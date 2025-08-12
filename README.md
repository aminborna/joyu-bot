ربات تلگرامی جویو (Joyu) برای مانیتورینگ دامنه‌ها (DNS, TCP, TLS, HTTP) و ارسال گزارش به تلگرام.

## 📌 ویژگی‌ها
- اضافه/حذف دامنه از طریق تلگرام
- نمایش وضعیت لحظه‌ای دامنه‌ها
- ارسال گزارش دوره‌ای
- مدیریت ادمین‌ها (سودو و معمولی)
- اجرای خودکار به‌عنوان سرویس systemd

## 🚀 نصب و راه‌اندازی سریع
برای نصب سریع و خودکار، کافی است دستور زیر را در ترمینال سرور خود اجرا کنید:

```bash
bash <(curl -Ls https://raw.githubusercontent.com/aminborna/joyu_bot/main/install.sh)
```

## 📂 مسیر فایل‌ها
- مسیر نصب: `/root/joyu_bot`
- فایل لاگ: `/root/joyu_bot/joyu.log`
- فایل سرویس systemd: `/etc/systemd/system/joyu_bot.service`

## 🛠 مدیریت سرویس
- مشاهده وضعیت سرویس:
```bash
systemctl status joyu_bot --no-pager
```
- شروع سرویس:
```bash
systemctl start joyu_bot
```
- توقف سرویس:
```bash
systemctl stop joyu_bot
```
- ریستارت سرویس:
```bash
systemctl restart joyu_bot
```
- مشاهده لاگ‌ها:
```bash
journalctl -u joyu_bot -f
```