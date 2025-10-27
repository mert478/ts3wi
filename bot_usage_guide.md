# Gelişmiş MegaTrend Bot - Kullanım Rehberi

## 🚀 Hızlı Başlangıç

### 1. Botu Çalıştırma
```bash
python integrated_megatrend_bot.py
```

### 2. Yeni Özellikler

#### ✅ **Risk Yönetimi**
- **Drawdown Kontrolü**: Maksimum %20 kayıp limiti
- **Günlük Zarar Limiti**: Günlük %5 kayıp limiti
- **Otomatik Günlük Sıfırlama**: Her gün gece yarısı sıfırlanır

#### ✅ **Market Filtreleri**
- **Trading Saatleri**: Sadece Londra (08:00-17:00 GMT) ve New York (13:00-22:00 GMT) seanslarında
- **Hafta Sonu Filtresi**: Cumartesi-Pazar işlem yapmaz
- **Volatilite Filtresi**: Aşırı volatil piyasalarda durur
- **Spread Filtresi**: Yüksek spread durumunda bekler

#### ✅ **Gelişmiş Sinyal Sistemi**
- **RSI Konfirmasyonu**: Aşırı alım/satım seviyelerini kontrol eder
- **MACD Konfirmasyonu**: Momentum değişimlerini yakalar
- **Bollinger Bands**: Fiyat bantlarına göre sinyal güçlendirir

#### ✅ **Veritabanı Kaydı**
- Tüm işlemler SQLite veritabanına kaydedilir
- Performans analizi için veri saklanır
- `enhanced_trading_bot.db` dosyasında veriler tutulur

## 📊 Yeni Log Sistemi

Bot artık daha detaylı loglar tutuyor:

```
2024-01-15 10:30:15 - INFO - Gelişmiş MegaTrend Bot başlatıldı...
2024-01-15 10:30:16 - INFO - Veritabanı başarıyla başlatıldı
2024-01-15 10:30:17 - INFO - MT5 bağlantısı başarılı - Hesap: 12345, Bakiye: 10000.00
2024-01-15 10:30:45 - INFO - Sinyal tespit edildi: BUY (Güç: 6)
2024-01-15 10:30:46 - INFO - BUY emri başarılı - SL: 2645.50000, TP: 2650.00000
2024-01-15 10:30:46 - INFO - İşlem veritabanına kaydedildi: BUY
```

## ⚙️ Parametreleri Özelleştirme

Bot başlatırken parametreleri değiştirebilirsiniz:

```python
bot = EnhancedMegaTrendBot(
    symbol="XAUUSD",           # İşlem yapılacak sembol
    timeframe=mt5.TIMEFRAME_M5, # Zaman dilimi
    lot_size=0.01              # Lot büyüklüğü
)

# Risk parametrelerini değiştirmek için:
bot.risk_manager.max_drawdown_percent = 15.0    # %15 maksimum drawdown
bot.risk_manager.daily_loss_limit_percent = 3.0 # %3 günlük limit
```

## 📈 Performans İzleme

### Veritabanından Veri Okuma
```python
import sqlite3
import pandas as pd

# Veritabanı bağlantısı
conn = sqlite3.connect('enhanced_trading_bot.db')

# Tüm işlemleri görüntüle
trades_df = pd.read_sql_query("SELECT * FROM trades ORDER BY timestamp DESC", conn)
print(trades_df.head())

# Günlük performansı görüntüle
daily_df = pd.read_sql_query("SELECT * FROM daily_performance ORDER BY date DESC", conn)
print(daily_df.head())

conn.close()
```

## 🔧 Sorun Giderme

### 1. "MT5 başlatılamadı" Hatası
- MetaTrader 5'in açık olduğundan emin olun
- Algoritmic trading'in etkin olduğunu kontrol edin
- MT5'te hesabınıza giriş yaptığınızdan emin olun

### 2. "Veritabanı kayıt hatası"
- Dosya yazma yetkilerinizi kontrol edin
- Disk alanının yeterli olduğundan emin olun

### 3. "Market saatleri dışında" Mesajı
- Normal durum, bot sadece major market saatlerinde çalışır
- Test etmek için `is_trading_time()` fonksiyonunu geçici olarak `return True` yapabilirsiniz

### 4. "Yüksek volatilite tespit edildi"
- Normal durum, bot güvenlik için aşırı volatil zamanlarda durur
- Volatilite eşiğini değiştirmek için `volatility_threshold` parametresini artırın

## 📋 Önemli Notlar

### Güvenlik
- ✅ Drawdown koruması aktif
- ✅ Günlük zarar limiti aktif
- ✅ Market saatleri filtresi aktif
- ✅ Volatilite filtresi aktif

### Performans
- Bot her 5 saniyede bir kontrol yapar
- Market filtrelerine takıldığında 30 saniye bekler
- Risk kontrolü başarısız olduğunda 60 saniye bekler

### Veri Saklama
- Tüm işlemler veritabanına kaydedilir
- Log dosyası: `enhanced_bot.log`
- Veritabanı dosyası: `enhanced_trading_bot.db`

## 🎯 Sonraki Adımlar

1. **Backtesting**: Geçmiş verilerle test yapın
2. **Parametre Optimizasyonu**: En iyi ayarları bulun
3. **Multi-Symbol**: Birden fazla sembol ekleyin
4. **Dashboard**: Web tabanlı izleme paneli ekleyin

Bu gelişmiş bot, orijinal botunuzun tüm özelliklerini koruyarak kritik güvenlik ve performans iyileştirmeleri ekler. Güvenle kullanabilirsiniz!