# EĞER HALA ZARAR EDİYORSA BU AYARLARI UYGULA:

# profitable_scalping_bot.py dosyasının içinde şu değişiklikleri yap:

# 1. DAHA KONSERVATIF AYARLAR
self.take_profit_pips = 8        # 6'dan 8'e çıkar
self.stop_loss_pips = 3          # 4'ten 3'e düşür → 1:2.6 R/R
self.quick_profit_pips = 2       # 3'ten 2'ye düşür (daha hızlı kapat)

# 2. DAHA SIKI FİLTRELER  
self.min_trend_strength = 0.5    # 0.3'ten 0.5'e (daha güçlü trend)
self.min_price_move = 0.3        # 0.2'den 0.3'e (daha büyük hareket)
self.max_spread = 1.0            # 1.5'ten 1.0'a (daha dar spread)

# 3. TEK POZİSYON
self.max_positions = 1           # 2'den 1'e (daha güvenli)

# 4. M5 TIMEFRAME DENEYEBİLİRSİN
timeframe=mt5.TIMEFRAME_M5       # M1 yerine M5 (daha az gürültü)

print("🔧 ULTRA KONSERVATIF AYARLAR AKTİF!")
print("🎯 R/R: 1:2.6 (çok yüksek)")
print("⚡ 2 pip'te hızlı kapat")
print("🛡️ Tek pozisyon (düşük risk)")