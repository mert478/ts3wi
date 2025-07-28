# MEVCUT BOTUNUZU BU AYARLARLA DEĞİŞTİRİN - ÇOK SIK TİCARET İÇİN

if __name__ == "__main__":
    # 🔥 ULTRA AGRESIF SETTİNGS
    bot = ImprovedMegaTrendBot(
        symbol="XAUUSD+",
        timeframe=mt5.TIMEFRAME_M1,  # 1 dakika - çok hızlı
        initial_lot_size=0.01,
        risk_per_trade=0.002,  # %0.2 düşük risk
        enable_spread_filter=False  # Spread kontrolü tamamen kapat
    )
    
    # 🚀 MANUEEL OVERRIDE - EN AGRESIF AYARLAR
    bot.min_signal_strength = 1           # 3'ten 1'e - HER SİNYALİ KABUL ET
    bot.max_positions = 15                # 3'ten 15'e - ÇOK FAZLA POZİSYON
    bot.max_daily_loss = 20.0            # Düşük günlük limit
    bot.atr_multiplier = 0.5             # 2.0'dan 0.5'e - ÇOK DAR STOP
    
    # RSI'yı tamamen devre dışı bırak
    bot.rsi_overbought = 95              # 70'den 95'e - neredeyse hiç engel
    bot.rsi_oversold = 5                 # 30'dan 5'e - neredeyse hiç engel
    
    # Moving average periyotlarını çok düşür
    bot.media1_period = 2                # 10'dan 2'ye - ÇOK HIZLI
    bot.media2_period = 5                # 20'den 5'e - ÇOK HIZLI  
    bot.media3_period = 10               # 50'den 10'a - HIZLI
    
    # ATR ve RSI periyotlarını düşür
    bot.atr_period = 3                   # 10'dan 3'e - ÇOK HIZLI
    bot.rsi_period = 5                   # 14'ten 5'e - ÇOK HIZLI
    
    # Sinyal cooldown'ı çok düşür
    bot.signal_cooldown = 10             # 120'den 10'a - 10 SANİYE BEKLE
    
    # Market filtrelerini devre dışı bırak
    bot.adaptive_mode = False            # Adaptif mod kapalı
    bot.enable_spread_filter = False     # Spread kontrolü kapalı
    
    # Pozisyon sizing'i daha agresif yap
    bot.min_lot_size = 0.01              # Minimum lot
    bot.max_lot_size = 0.05              # Maksimum lot düşür
    
    # Pivot ve S/R ayarlarını gevşet
    bot.min_strength = 1                 # 2'den 1'e
    bot.pivot_period = 3                 # 10'dan 3'e
    bot.channel_width = 50               # 10'dan 50'ye - ÇOK GENİŞ
    
    # Stop loss / take profit'i dar yap (scalping)
    # Bu metodu override et
    def ultra_narrow_stop_take(self, signal_data):
        current_price = signal_data['price']
        signal = signal_data['signal']
        
        # Çok dar stop/take - sabit pip
        pip_size = 0.0001  # XAUUSD için
        stop_pips = 3      # 3 pip stop
        take_pips = 2      # 2 pip take (negatif R:R bile olsa)
        
        if signal in ["BUY", "STRONG_BUY"]:
            stop_loss = current_price - (stop_pips * pip_size)
            take_profit = current_price + (take_pips * pip_size)
        else:
            stop_loss = current_price + (stop_pips * pip_size)
            take_profit = current_price - (take_pips * pip_size)
        
        return stop_loss, take_profit
    
    # Metodu değiştir
    bot.calculate_dynamic_stop_take_profit = ultra_narrow_stop_take
    
    # Market hours kontrolünü tamamen kaldır
    def always_suitable(self):
        """Her zaman trade'e uygun"""
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return False
            
            # Sadece günlük kayıp kontrolü
            today = datetime.now().strftime('%Y-%m-%d')
            daily_pnl = self.performance_tracker.daily_pnl.get(today, 0)
            if daily_pnl < -self.max_daily_loss:
                return False
            
            return True
        except:
            return True
    
    bot.is_market_suitable = always_suitable
    
    print("🔥🔥🔥 ULTRA AGRESIF SETTİNGS AKTİF! 🔥🔥🔥")
    print(f"⚡ Min sinyal gücü: {bot.min_signal_strength} (Her sinyal kabul)")
    print(f"⚡ Max pozisyon: {bot.max_positions} (Çok fazla)")
    print(f"⚡ ATR çarpanı: {bot.atr_multiplier} (Çok dar stop)")
    print(f"⚡ Sinyal cooldown: {bot.signal_cooldown}s (Çok hızlı)")
    print(f"⚡ MA periyotları: {bot.media1_period}, {bot.media2_period}, {bot.media3_period}")
    print(f"⚡ RSI aralığı: {bot.rsi_oversold}-{bot.rsi_overbought} (Çok gevşek)")
    print("🎯 Her küçük fiyat hareketinde trade açacak!")
    print("⚠️  Risk: Bu ayarlar çok agresif - dikkatli kullanın!")
    
    bot.run_bot()