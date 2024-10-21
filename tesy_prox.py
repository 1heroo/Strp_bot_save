import requests


# Функция для проверки прокси
def check_proxy(proxy_url):
    try:
        proxies = {
            "http": proxy_url,
            "https": proxy_url
        }
        # Отправляем запрос к сайту через прокси, например google.com
        response = requests.get('http://www.google.com', proxies=proxies, timeout=5)

        # Если статус код 200, то прокси рабочий
        if response.status_code == 200:
            return True
    except Exception as e:
        # Если возникло исключение, то прокси нерабочий
        return False


# Функция для проверки всех прокси из файла
def check_proxies_from_file(file_path):
    with open(file_path, 'r') as file:
        proxies = file.readlines()

    non_working_proxies = []

    # Проверяем каждый прокси
    for proxy in proxies:
        proxy = proxy.strip()  # Убираем лишние пробелы и переносы строк
        if not check_proxy(proxy):
            non_working_proxies.append(proxy)

    # Выводим список нерабочих прокси
    if non_working_proxies:
        print("Нерабочие прокси:")
        for proxy in non_working_proxies:
            print(proxy)
    else:
        print("Все прокси рабочие.")


# Путь к файлу с прокси
file_path = 'proxies.txt'
check_proxies_from_file(file_path)
