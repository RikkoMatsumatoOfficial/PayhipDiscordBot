import os
import configparser
import requests
import discord
import dearpygui.dearpygui as dpg
from discord.ext import tasks
from typing import List, Dict
from dataclasses import dataclass
from threading import Thread
from collections import deque

# Configuration
config = configparser.ConfigParser()
config.read('config.ini')

@dataclass
class PayhipOrder:
    id: str
    status: str
    total: str
    customer_email: str
    items: List[Dict[str, str]]

class PayhipMonitor:
    def __init__(self):
        self.payhip_key = config['API']['PAYHIP_KEY']
        self.discord_token = config['API']['DISCORD_TOKEN']
        self.channel_id = int(config['API']['CHANNEL_ID'])
        self.poll_interval = int(config['Settings']['POLL_INTERVAL'])
        self.processed_orders = set()
        self.bot_running = False
        self.gui_log = deque(maxlen=50)  # Fixed-size log
        self.log_content = ""

        # Discord bot setup
        intents = discord.Intents.default()
        self.bot = discord.Client(intents=intents)
        self.setup_bot_events()

    def setup_bot_events(self):
        @self.bot.event
        async def on_ready():
            self.log("Discord Bot Connected")
            self.check_orders.start()

        @tasks.loop(seconds=self.poll_interval)
        async def check_orders():
            orders = self.fetch_orders()
            if not (channel := self.bot.get_channel(self.channel_id)):
                return

            for order in orders:
                if order.status == "completed" and order.id not in self.processed_orders:
                    await self.send_notification(channel, order)
                    self.processed_orders.add(order.id)
                    self.log(f"New Order: {order.id}")

        self.check_orders = check_orders

    def fetch_orders(self) -> List[PayhipOrder]:
        try:
            response = requests.get(
                "https://payhip.com/api/v1/orders",
                headers={"Authorization": f"Bearer {self.payhip_key}"},
                params={"limit": 5},
                timeout=10
            )
            response.raise_for_status()
            return [
                PayhipOrder(
                    id=order["id"],
                    status=order["status"],
                    total=order["total"],
                    customer_email=order["customer_email"],
                    items=order.get("items", [])
                )
                for order in response.json().get("data", [])
            ]
        except Exception as e:
            self.log(f"API Error: {str(e)}")
            return []

    async def send_notification(self, channel, order: PayhipOrder):
        embed = discord.Embed(
            title="Someone is buying you're digital product!!!",
            color=discord.Color.green(),
            description=f"**Order ID:** `{order.id}`"
        )
        embed.add_field(name="Total: ", value=f"${order.total}")
        embed.add_field(name="Customer(EMAIL): ", value=order.customer_email)
        
        if order.items:
            products = "\n".join(f"- {item.get('product_name', 'Unknown')}" for item in order.items)
            embed.add_field(name="Products(this is what you're customer is bought)", value=products, inline=False)
        
        await channel.send(embed=embed)

    def log(self, message: str):
        self.gui_log.append(message)
        self.log_content = "\n".join(self.gui_log)
        
        # Auto-scroll by forcing focus to last item
        if dpg.does_item_exist("log_content"):
            dpg.set_value("log_content", self.log_content)
            dpg.focus_item("log_content")  # Alternative to scrolling
    def run_bot(self):
        self.bot_running = True
        self.log("Starting Discord bot...")
        try:
            self.bot.run(self.discord_token)
        except Exception as e:
            self.log(f"Bot error: {str(e)}")
            self.bot_running = False

    def stop_bot(self):
        """Properly shutdown the Discord bot"""
        if not self.bot_running:
            return
            
        self.log("Stopping bot...")
        self.bot_running = False
        
        # Stop the order checking loop
        if hasattr(self, 'check_orders'):
            self.check_orders.stop()
        
        # Close the Discord connection
        if not self.bot.is_closed():
            Thread(target=self.bot.close).start()
        
        self.log("Bot stopped successfully")

def main():
    monitor = PayhipMonitor()

    dpg.create_context()
    dpg.create_viewport(title="Payhip Discord Bot by RikkoMatsumatoOfficial", width=800, height=600)

    with dpg.window(label="Main Window", tag="main_window"):
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Start Bot",
                callback=lambda: Thread(target=monitor.run_bot).start()
            )
            dpg.add_button(
                label="Stop Bot",
                callback=monitor.stop_bot
            )
        
        with dpg.child_window(height=400):
            dpg.add_input_text(
                multiline=True,
                readonly=True,
                tag="log_content",
                width=-1,
                height=-1
            )

    dpg.setup_dearpygui()
    dpg.show_viewport()
    dpg.set_primary_window("main_window", True)

    while dpg.is_dearpygui_running():
        dpg.render_dearpygui_frame()

    dpg.destroy_context()

if __name__ == "__main__":
    main()
