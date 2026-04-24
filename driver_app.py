# driver_app.py
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.scrollview import ScrollView
import requests

SERVER_URL = "http://10.66.144.191:5000"

class DriverApp(App):
    def build(self):
        self.layout = BoxLayout(orientation="vertical", padding=10, spacing=10)
        self.selected = []
        self.products = []

        label = Label(text="Select Products for Delivery", font_size=22)
        self.layout.add_widget(label)

        self.scroll = ScrollView(size_hint=(1, 0.7))
        self.btn_layout = BoxLayout(orientation="vertical", size_hint_y=None, spacing=5)
        self.btn_layout.bind(minimum_height=self.btn_layout.setter("height"))
        self.scroll.add_widget(self.btn_layout)
        self.layout.add_widget(self.scroll)

        send_btn = Button(text="Send Selection", size_hint=(1, 0.2))
        send_btn.bind(on_press=self.send_selection)
        self.layout.add_widget(send_btn)

        self.load_products()
        return self.layout

    def load_products(self):
        try:
            r = requests.get(SERVER_URL + "/get_products")
            if r.status_code == 200:
                self.products = r.json()
                for p in self.products:
                    btn = ToggleButton(text=p, size_hint_y=None, height=50)
                    btn.bind(on_press=self.toggle_product)
                    self.btn_layout.add_widget(btn)
        except Exception as e:
            self.layout.add_widget(Label(text=f"Error loading products: {e}"))

    def toggle_product(self, instance):
        if instance.state == "down":
            self.selected.append(instance.text)
        else:
            self.selected.remove(instance.text)

    def send_selection(self, instance):
        try:
            r = requests.post(SERVER_URL + "/set_products", json={"products": self.selected})
            if r.status_code == 200:
                instance.text = "✅ Sent Successfully!"
            else:
                instance.text = "❌ Server Error"
        except Exception as e:
            instance.text = f"⚠️ {e}"

DriverApp().run()
