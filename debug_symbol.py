import MetaTrader5 as mt5
import pandas as pd
from datetime import datetime

def debug_symbol_data():
    # MT5 başlat
    if not mt5.initialize():
        print("MT5 başlatılamadı!")
        return
    
    symbol = "XAUUSD+"
    timeframe = mt5.TIMEFRAME_M15
    
    print(f"=== {symbol} Symbol Debug ===")
    
    # 1. Symbol bilgilerini kontrol et
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        print(f"❌ {symbol} sembolü bulunamadı!")
        
        # Alternatif semboller dene
        alternatives = ["XAUUSD", "GOLD", "XAU/USD", "XAU-USD"]
        print("\n🔍 Alternatif semboller kontrol ediliyor:")
        
        for alt_symbol in alternatives:
            alt_info = mt5.symbol_info(alt_symbol)
            if alt_info is not None:
                print(f"✅ {alt_symbol} bulundu!")
                symbol = alt_symbol
                break
            else:
                print(f"❌ {alt_symbol} bulunamadı")
    else:
        print(f"✅ {symbol} sembolü bulundu!")
        print(f"   - Visible: {symbol_info.visible}")
        print(f"   - Point: {symbol_info.point}")
        print(f"   - Digits: {symbol_info.digits}")
    
    # 2. Symbol'ü seç
    if not mt5.symbol_select(symbol, True):
        print(f"❌ {symbol} seçilemedi!")
        mt5.shutdown()
        return
    
    # 3. Tick verilerini kontrol et
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        print(f"❌ {symbol} için tick verisi alınamadı!")
    else:
        print(f"✅ Tick verisi:")
        print(f"   - Ask: {tick.ask}")
        print(f"   - Bid: {tick.bid}")
        print(f"   - Spread: {(tick.ask - tick.bid) / symbol_info.point:.1f} points")
    
    # 4. Historical data kontrol et
    print(f"\n📊 Historical data kontrolü:")
    
    # Farklı bar sayıları dene
    for bars in [10, 50, 100, 500]:
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, bars)
        if rates is None or len(rates) == 0:
            print(f"❌ {bars} bar alınamadı")
        else:
            print(f"✅ {bars} bar alındı - Son veri: {pd.to_datetime(rates[-1]['time'], unit='s')}")
            
            # İlk 10 veriyi göster
            if bars == 10:
                df = pd.DataFrame(rates)
                df['time'] = pd.to_datetime(df['time'], unit='s')
                print("\n📋 İlk 10 bar:")
                print(df[['time', 'open', 'high', 'low', 'close', 'tick_volume']].head())
            break
    
    # 5. Farklı timeframe'ler dene
    print(f"\n⏰ Timeframe kontrolü:")
    timeframes = [
        (mt5.TIMEFRAME_M1, "M1"),
        (mt5.TIMEFRAME_M5, "M5"), 
        (mt5.TIMEFRAME_M15, "M15"),
        (mt5.TIMEFRAME_H1, "H1")
    ]
    
    for tf_value, tf_name in timeframes:
        rates = mt5.copy_rates_from_pos(symbol, tf_value, 0, 10)
        if rates is None or len(rates) == 0:
            print(f"❌ {tf_name} timeframe veri yok")
        else:
            print(f"✅ {tf_name} timeframe - {len(rates)} bar")
    
    # 6. Market saatleri kontrolü
    now = datetime.now()
    print(f"\n🕐 Market durumu:")
    print(f"   - Şu anki zaman: {now}")
    print(f"   - UTC saat: {datetime.utcnow().hour}")
    
    mt5.shutdown()

if __name__ == "__main__":
    debug_symbol_data()