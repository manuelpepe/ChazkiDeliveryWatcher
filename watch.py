from __future__ import annotations

import os
import time
import argparse

from datetime import datetime, timedelta
from dataclasses import dataclass

import pywhatkit

from selenium import webdriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def _safe_find(
    driver: WebDriver | WebElement,
    *args,
    method: str = "find_elements",
    timeout: int = 40,
):
    WebDriverWait(driver, timeout).until(EC.presence_of_element_located(args))
    return getattr(driver, method)(*args)


def _clear_console() -> None:
    if os.name == "nt":
        os.system("cls")
    else:
        os.system("clear")


@dataclass
class Entry:
    date: str
    location: str
    message: str


def _parse_entry(columns: list[WebElement]) -> Entry:
    date = columns[0].text
    time = columns[1].text
    location = columns[2].text
    message = columns[3].text
    return Entry(
        date=f"{date} {time}",
        location=location,
        message=message,
    )


class Watcher:
    def __init__(
        self, driver: WebDriver, code: str, sleep: int, recipient: str | None = None
    ):
        self.driver: WebDriver = driver
        self.code = code
        self.sleep = sleep
        self.recipient = recipient
        self._entries: list[Entry] = []
        self._url = f"https://apps.chazki.com/tracker/{self.code}"
        self._timedelta = timedelta(seconds=self.sleep)

    @property
    def entries(self) -> list[Entry]:
        return self._entries

    @entries.setter
    def entries(self, new_entries: list[Entry]) -> None:
        added = []
        for entry in new_entries:
            if entry not in self._entries:
                added.append(entry)
        if added:
            self._notify(added)
        self._entries = new_entries

    def watch(self) -> None:
        while True:
            self.entries = self._find_entries()
            self._print_entries()
            time.sleep(self.sleep)

    def _find_entries(self) -> list[Entry]:
        entries = []
        self.driver.get(self._url)
        logs = _safe_find(self.driver, By.ID, "logs", method="find_element")
        rows = _safe_find(logs, By.TAG_NAME, "tr")
        for element in rows:
            columns = element.find_elements(By.TAG_NAME, "td")
            if columns:
                entry = _parse_entry(columns)
                entries.append(entry)
        return entries

    def _print_entries(self) -> None:
        curdate = datetime.now()
        next_update = curdate + self._timedelta
        _clear_console()
        print(f"URL: {self._url}\n")
        for entry in self.entries:
            print(entry)
        print()
        print(f"Last refresh at: {curdate.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Next refresh at {next_update.strftime('%Y-%m-%d %H:%M:%S')}")

    def _notify(self, new_entries: list[Entry]) -> None:
        if self.recipient:
            msg = "Update in your delivery!\n\n"
            for entry in new_entries:
                msg += f"  - {entry}\n"
            msg += f"\nURL: {self._url}"
            print("Sending notification...")
            pywhatkit.sendwhatmsg_instantly(self.recipient, msg, wait_time=20)
            print("Notification sent...")
            time.sleep(3)


def _chrome_driver(headless: bool = False) -> webdriver.Chrome:
    from selenium.webdriver.chrome.service import Service as ChromeService
    from selenium.webdriver.chrome.options import Options
    from webdriver_manager.chrome import ChromeDriverManager

    opts = Options()
    if headless:
        print(
            "WARNING: Headless mode on Chrome might break. Turn off with -H parameter."
        )
        opts.headless = True
    service = ChromeService(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=opts)


def _firefox_driver(headless: bool = False) -> webdriver.Firefox:
    from selenium.webdriver.firefox.service import Service as FirefoxService
    from selenium.webdriver.firefox.options import Options
    from webdriver_manager.firefox import GeckoDriverManager

    service = FirefoxService(GeckoDriverManager().install())
    opts = Options()
    if headless:
        opts.headless = True
    return webdriver.Firefox(service=service, options=opts)


DRIVERS = {
    "chrome": _chrome_driver,
    "firefox": _firefox_driver,
}


def parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scan your chazki delivery for updates"
    )
    parser.add_argument("code", type=str, help="Tracking code for your order")
    parser.add_argument(
        "-b",
        "--browser",
        help="Browser driver to be used",
        type=str,
        default="firefox",
        choices=DRIVERS.keys(),
        required=False,
    )
    parser.add_argument(
        "-t",
        "--timeout",
        help="Seconds to sleep between refreshes",
        type=int,
        default=60 * 5,
        required=False,
    )
    parser.add_argument(
        "-n",
        "--notify",
        help="Whatsapp number to be notified when entries are added",
        type=str,
        default="",
        required=False,
    )
    parser.add_argument(
        "-H",
        "--headless",
        help="Disable headless mode (show browser GUI)",
        action="store_false",
    )
    return parser


def main():
    args = parser().parse_args()
    driver_factory = DRIVERS[args.browser]
    driver = driver_factory(args.headless)
    watcher = Watcher(driver, args.code, args.timeout, args.notify)
    watcher.watch()


if __name__ == "__main__":
    main()
