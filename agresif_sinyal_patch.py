# MEVCUT BOTUNUZUN generate_enhanced_signals METODUNU BU İLE DEĞİŞTİRİN

def generate_ultra_aggressive_signals(self, df: pd.DataFrame) -> Optional[Dict]:
    """ULTRA AGRESIF SİNYAL ÜRETİMİ - ÇOK SIK TRADİNG"""
    
    if len(df) < 5:  # Çok az veri bile yeterli
        return None
    
    close = df['close'].values
    current_price = close[-1]
    current_time = df['time'].iloc[-1]
    
    # 🚀 BASIT FİYAT HAREKETİ ANALİZİ
    signal = None
    signal_strength = 1  # Her zaman en az 1
    
    # Son 3 barın fiyat hareketine bak
    if len(close) >= 3:
        price_1 = close[-1]  # Şu anki
        price_2 = close[-2]  # 1 önceki  
        price_3 = close[-3]  # 2 önceki
        
        # Basit momentum - 2 bardan fazla aynı yönde hareket
        upward_momentum = price_1 > price_2 > price_3
        downward_momentum = price_1 < price_2 < price_3
        
        # Son bar'da küçük bir hareket bile yeterli
        last_change = price_1 - price_2
        change_threshold = 0.00001  # 0.01 pip bile yeter!
        
        if upward_momentum or last_change > change_threshold:
            signal = "BUY"
            signal_strength = 2
        elif downward_momentum or last_change < -change_threshold:
            signal = "SELL"
            signal_strength = 2
    
    # ⚡ VOLUME BOOST - Volume varsa sinyal güçlendir
    if len(df) >= 2:
        current_volume = df['tick_volume'].iloc[-1]
        prev_volume = df['tick_volume'].iloc[-2]
        
        if current_volume > prev_volume:
            signal_strength += 1
    
    # 🎯 ÇOK BASIT MA KONTROLÜ (opsiyonel güçlendirme)
    if len(df) >= 5:
        try:
            ma3 = df['close'].rolling(3).mean().iloc[-1]
            ma5 = df['close'].rolling(5).mean().iloc[-1]
            
            if signal == "BUY" and current_price > ma3:
                signal_strength += 1
            elif signal == "SELL" and current_price < ma3:
                signal_strength += 1
        except:
            pass  # MA hesaplanamasa bile sinyal ver
    
    # 🔥 COOLDOWN KONTROLÜ - ÇOK KISA
    if hasattr(self, 'last_signal_time') and self.last_signal_time:
        time_diff = (current_time - self.last_signal_time).total_seconds()
        if time_diff < 10:  # 10 saniye bekle
            return None
    
    # ✅ SİNYAL OLUŞTUR - ÇOK KOLAY KOŞULLAR
    if signal and signal_strength >= 1:  # Her sinyal geçerli
        self.last_signal_time = current_time
        
        # RSI hesapla (filtreleme için değil, bilgi için)
        rsi = 50  # Default
        if len(close) >= 5:
            try:
                rsi_values = talib.RSI(close, timeperiod=5)
                rsi = rsi_values[-1] if len(rsi_values) > 0 and not np.isnan(rsi_values[-1]) else 50
            except:
                rsi = 50
        
        print(f"🎯 AGRESIF SİNYAL: {signal} | Güç: {signal_strength} | Fiyat: {current_price:.5f} | RSI: {rsi:.1f}")
        
        return {
            'signal': signal,
            'strength': signal_strength,
            'price': current_price,
            'rsi': rsi,
            'ma1': current_price,  # Basit değerler
            'ma2': current_price,
            'ma3': current_price,
            'supertrend': current_price,
            'trend': 1 if signal == "BUY" else -1,
            'sr_levels': [],
            'supply_zones': [],
            'demand_zones': [],
            'atr': 0.001  # Minimal ATR
        }
    
    return None

# KULLANIMI:
# Mevcut botunuzda bu satırı ekleyin:
# bot.generate_enhanced_signals = generate_ultra_aggressive_signals

# Veya doğrudan metodun adını değiştirin: