from requests import get

token = "6874396479:AAETyIiiUhpR-pJlW7cwcX0Sd59yDI8jqVc"
print(get(f'http://api.telegram.org/bot{token}/getUpdates?offset={str(600)}').json(), f'http://api.telegram.org/bot{token}/getUpdates?offset={str(1)}')