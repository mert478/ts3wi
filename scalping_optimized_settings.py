# SCALPING İÇİN OPTİMİZE EDİLMİŞ AYARLAR

# Mevcut bot'unuzu şu ayarlarla değiştirin:

if __name__ == "__main__":
    # SCALPING AYARLARI
    bot = ImprovedMegaTrendBot(
        symbol="XAUUSD+",
        timeframe=mt5.TIMEFRAME_M1,  # veya M5
        initial_lot_size=0.01,
        risk_per_trade=0.005,  # %0.5 risk (daha sık işlem için düşük)
        enable_spread_filter=False
    )
    
    # 🔥 SCALPING İÇİN GEVŞEK AYARLAR
    bot.min_signal_strength = 1           # 3'ten 1'e düşür (çok daha kolay sinyal)
    bot.max_positions = 5                 # 2'den 5'e çıkar (daha fazla pozisyon)
    bot.max_daily_loss = 20.0            # Günlük risk düşür
    bot.atr_multiplier = 1.0             # Dar stop loss (2.0'dan 1.0'a)
    
    # RSI seviyelerini gevşet (daha sık sinyal için)
    bot.rsi_overbought = 80              # 70'den 80'e
    bot.rsi_oversold = 20                # 30'dan 20'ye
    
    # Take profit'i küçült (scalping için)
    bot.risk_reward_ratio = 1.5          # 2.0'dan 1.5'e (1:1.5)
    
    print("[SCALPING] Gevşek ayarlar aktif!")
    print(f"[SCALPING] Min sinyal gücü: {bot.min_signal_strength}")
    print(f"[SCALPING] Max pozisyon: {bot.max_positions}")
    print(f"[SCALPING] ATR çarpanı: {bot.atr_multiplier}")
    
    bot.run_bot()