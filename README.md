# tgmuxbot

Multiplexes incoming messages into a single chat with a topic per sender (works in the other direction as well).

---

Для запуска необходимо собрать проект

`poetry build`

В папке `dist` появится файл `chat_bot-1.0.0.tar.gz`. На сервере установите этот файл

`pip install dist/chat_bot-1.0.0.tar.gz`

Далее создайте файл `config.json`, используя в качестве основы файл `config.example.json`

После чего отредактируйте файл `multichatbot.service`, заменив в строках 7 8 и 9 `/home/root` и `root` на вашу папку и пользователя соответственно

Теперь сервис можно добавить в `systemctl`

```
sudo cp multichatbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable multichatbot.service
sudo systemctl start multichatbot.service
```

Можно проверить сервис командой

`
sudo systemctl status multichatbot.service
`
