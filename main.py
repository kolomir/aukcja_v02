import sys
import mysql.connector
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt5.QtCore import QDateTime, QTimer
from PyQt5.QtGui import QPixmap
from main2_ui import Ui_MainWindow  # Import wygenerowanego szablonu


class AuctionApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Połączenie z bazą danych
        self.conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="",
            database="auction_app"
        )
        self.cursor = self.conn.cursor()

        self.current_item = None
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_time_remaining)

        # Podłączenie funkcji do elementów interfejsu
        self.ui.item_list.currentRowChanged.connect(self.display_item_details)
        self.ui.status_filter.currentIndexChanged.connect(self.load_items)
        self.ui.bid_button.clicked.connect(self.place_bid)

        # Wczytanie danych
        self.load_items()

    def load_items(self):
        status = self.ui.status_filter.currentText()
        print(f"DEBUG: Wybrany status: {status}")

        # Warunki filtrowania
        conditions = []
        if status == "Aktywne":
            conditions.append("is_active = TRUE AND is_archived = FALSE")
        elif status == "Zamknięte":
            conditions.append("is_active = FALSE AND is_archived = FALSE")
        elif status == "Archiwalne":
            conditions.append("is_archived = TRUE")

        # Budowanie zapytania SQL
        query = "SELECT id, name, price, image_path, end_date, end_time, bid_step, is_active, is_archived FROM items"
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        print(f"DEBUG: Zapytanie SQL: {query}")

        # Wykonanie zapytania
        try:
            self.cursor.execute(query)
            self.items = self.cursor.fetchall()
        except mysql.connector.Error as err:
            print(f"ERROR: {err}")
            self.items = []

        # Aktualizacja listy
        self.ui.item_list.clear()
        for item in self.items:
            self.ui.item_list.addItem(item[1])  # Dodanie nazwy przedmiotu do listy

        # Automatyczne wybranie pierwszego elementu
        if self.items:
            self.ui.item_list.setCurrentRow(0)
        else:
            self.clear_details()

    def on_status_change(self):
        """Obsługuje zmianę statusu aukcji."""
        self.load_items()

    def clear_details(self):
        """Czyści szczegóły wyświetlanego przedmiotu."""
        self.current_item = None
        self.ui.image_label.setText("Brak zdjęcia")
        self.ui.price_label.setText("Cena: -")
        self.ui.bid_increment_label.setText("Postęp licytacji: -")
        self.ui.time_label.setText("Czas do końca aukcji: -")
        self.ui.bid_button.setEnabled(False)

    def display_item_details(self, index):
        """Wyświetl szczegóły wybranego przedmiotu."""
        if index < 0 or index >= len(self.items):
            self.clear_details()
            return

        item = self.items[index]
        self.current_item = {
            "id": item[0],
            "name": item[1],
            "price": item[2],
            "image": item[3],
            "end_date": item[4],
            "end_time": item[5],
            "bid_step": item[6],
            "is_active": item[7],
            "is_archived": item[8],
        }

        # Wyświetl szczegóły
        self.ui.image_label.setPixmap(QPixmap(self.current_item["image"]).scaled(self.ui.image_label.size()))
        self.ui.price_label.setText(f"Cena: {self.current_item['price']} zł")
        self.ui.bid_increment_label.setText(f"Postęp licytacji: {self.current_item['bid_step']} zł")

        # Uruchom timer tylko dla aktywnych aukcji
        if self.current_item["is_active"]:
            self.update_time_remaining()
            self.timer.start(1000)
        else:
            self.ui.time_label.setText("Aukcja zakończona!")
            self.ui.bid_button.setEnabled(False)

        # Sprawdź status przycisku licytacji
        self.ui.bid_button.setEnabled(self.current_item["is_active"] and not self.current_item["is_archived"])

    def update_time_remaining(self):
        """Oblicz i wyświetl czas do końca aukcji."""
        if not self.current_item:
            return

        end_datetime = QDateTime.fromString(
            f"{self.current_item['end_date']} {self.current_item['end_time']}",
            "yyyy-MM-dd HH:mm:ss"
        )
        now = QDateTime.currentDateTime()

        if now >= end_datetime:
            self.cursor.execute(
                "UPDATE items SET is_active = FALSE WHERE id = %s",
                (self.current_item["id"],)
            )
            self.conn.commit()
            self.ui.time_label.setText("Aukcja zakończona!")
            self.ui.bid_button.setEnabled(False)
            self.timer.stop()
            return

        time_remaining = now.secsTo(end_datetime)
        hours = time_remaining // 3600
        minutes = (time_remaining % 3600) // 60
        seconds = time_remaining % 60

        self.ui.time_label.setText(f"Czas do końca aukcji: {hours:02}:{minutes:02}:{seconds:02}")

    def place_bid(self):
        """Zapisz nową licytację w bazie danych."""
        if not self.current_item:
            QMessageBox.warning(self, "Błąd", "Wybierz przedmiot z listy.")
            return

        name = self.ui.name_input.text().strip()
        if not name:
            QMessageBox.warning(self, "Błąd", "Podaj swoje imię i nazwisko.")
            return

        new_price = self.current_item["price"] + self.current_item["bid_step"]
        self.cursor.execute(
            "UPDATE items SET price = %s WHERE id = %s",
            (new_price, self.current_item["id"])
        )
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.cursor.execute(
            "INSERT INTO bids (item_id, bidder_name, bid_time, bid_amount) VALUES (%s, %s, %s, %s)",
            (self.current_item["id"], name, timestamp, new_price)
        )
        self.conn.commit()

        QMessageBox.information(self, "Sukces", f"Podbiłeś cenę przedmiotu: {self.current_item['name']}.")
        self.ui.name_input.clear()
        self.current_item["price"] = new_price
        self.ui.price_label.setText(f"Cena: {new_price} zł")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AuctionApp()
    window.show()
    sys.exit(app.exec_())
