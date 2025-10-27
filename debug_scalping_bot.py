import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
import talib

# Detaylı loglama
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class DebugScalpingBot:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M1):
        self.symbol = symbol
        self.timeframe = timeframe
        self.magic_number = 12345
        
        # ÇOOK GEVŞEK SCALPING AYARLARI
        self.lot_size = 0.01
        self.take_profit_pips = 3      # 3 pip hedef (daha kolay)
        self.stop_loss_pips = 8        # 8 pip stop
        self.max_positions = 5         # Max 5 pozisyon
        self.ema_fast = 3             # ÇOK HIZLI EMA (5'ten 3'e)
        self.ema_slow = 10            # ÇOK HIZLI EMA (20'den 10'a)
        
        self.logger = logging.getLogger(__name__)
        self.last_signal_time = None
        self.initialize_mt5()
    
    def initialize_mt5(self):
        """MT5 bağlantısı"""
        if not mt5.initialize():
            self.logger.error("MT5 başlatılamadı!")
            return False
        
        # Farklı symbol isimleri dene
        symbol_variants = [self.symbol, self.symbol + "+", "XAUUSD.", "GOLD"]
        
        for variant in symbol_variants:
            if mt5.symbol_select(variant, True):
                self.symbol = variant
                self.logger.info(f"✅ {self.symbol} bulundu ve seçildi!")
                break
        else:
            self.logger.error("Hiçbir GOLD symbolu bulunamadı!")
            return False
        
        # Test verisi
        test_data = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, 5)
        if test_data is None:
            self.logger.error("Test verisi alınamadı!")
            return False
        
        self.logger.info(f"✅ Test verisi OK: {len(test_data)} bar")
        return True
    
    def get_data(self, bars=30):
        """Veri al ve debug"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None:
            self.logger.error("❌ Veri alınamadı!")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        self.logger.debug(f"📊 Veri alındı: {len(df)} bar, Son fiyat: {df['close'].iloc[-1]:.5f}")
        return df
    
    def generate_simple_signal(self, df):
        """ÇOK BASİT SİNYAL - Aggressive EMA Crossover + Price Action"""
        if len(df) < self.ema_slow:
            self.logger.debug(f"❌ Yetersiz veri: {len(df)} < {self.ema_slow}")
            return None
        
        # EMA hesapla
        ema_fast = talib.EMA(df['close'].values, timeperiod=self.ema_fast)
        ema_slow = talib.EMA(df['close'].values, timeperiod=self.ema_slow)
        
        if len(ema_fast) < 2 or len(ema_slow) < 2:
            self.logger.debug("❌ EMA hesaplanamadı")
            return None
        
        current_fast = ema_fast[-1]
        current_slow = ema_slow[-1]
        prev_fast = ema_fast[-2]
        prev_slow = ema_slow[-2]
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        
        # Debug bilgileri
        self.logger.debug(f"📈 EMA Fast: {current_fast:.5f} (önceki: {prev_fast:.5f})")
        self.logger.debug(f"📈 EMA Slow: {current_slow:.5f} (önceki: {prev_slow:.5f})")
        self.logger.debug(f"💰 Fiyat: {current_price:.5f} (önceki: {prev_price:.5f})")
        
        # ÇOOK GEVŞEK SİNYALLER
        signal = None
        
        # 1. Klasik EMA Crossover
        if prev_fast <= prev_slow and current_fast > current_slow:
            signal = "BUY"
            self.logger.info(f"🟢 EMA CROSSOVER BUY: Fast({current_fast:.5f}) > Slow({current_slow:.5f})")
        elif prev_fast >= prev_slow and current_fast < current_slow:
            signal = "SELL" 
            self.logger.info(f"🔴 EMA CROSSOVER SELL: Fast({current_fast:.5f}) < Slow({current_slow:.5f})")
        
        # 2. EMA Üzerinde/Altında olmak (daha sık sinyal)
        elif current_price > current_fast > current_slow and prev_price <= prev_fast:
            signal = "BUY"
            self.logger.info(f"🟢 PRICE ABOVE EMA BUY: Price({current_price:.5f}) > EMA_Fast({current_fast:.5f})")
        elif current_price < current_fast < current_slow and prev_price >= prev_fast:
            signal = "SELL"
            self.logger.info(f"🔴 PRICE BELOW EMA SELL: Price({current_price:.5f}) < EMA_Fast({current_fast:.5f})")
        
        # 3. Momentum sinyali (fiyat hareketi)
        price_change = current_price - prev_price
        if abs(price_change) > 0.0001:  # En az 0.1 pip hareket
            if price_change > 0 and current_fast > current_slow:
                signal = "BUY"
                self.logger.info(f"🟢 MOMENTUM BUY: Fiyat yükseldi +{price_change:.5f}")
            elif price_change < 0 and current_fast < current_slow:
                signal = "SELL"
                self.logger.info(f"🔴 MOMENTUM SELL: Fiyat düştü {price_change:.5f}")
        
        if signal:
            return {
                'signal': signal,
                'price': current_price,
                'ema_fast': current_fast,
                'ema_slow': current_slow,
                'reason': 'Multiple conditions met'
            }
        else:
            self.logger.debug("⏳ Henüz sinyal yok, bekleniyor...")
            return None
    
    def count_positions(self):
        """Açık pozisyon sayısı"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            self.logger.debug("📊 Açık pozisyon yok")
            return 0
        
        my_positions = [p for p in positions if p.magic == self.magic_number]
        self.logger.debug(f"📊 Mevcut pozisyon sayısı: {len(my_positions)}")
        return len(my_positions)
    
    def place_order(self, signal_type):
        """Emir ver - DETAYLI DEBUG"""
        try:
            # Pozisyon kontrolü
            current_positions = self.count_positions()
            if current_positions >= self.max_positions:
                self.logger.warning(f"⚠️ Max pozisyon sayısına ulaşıldı: {current_positions}/{self.max_positions}")
                return False
            
            # Fiyat bilgisi
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                self.logger.error("❌ Tick bilgisi alınamadı!")
                return False
            
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                self.logger.error("❌ Symbol bilgisi alınamadı!")
                return False
            
            point = symbol_info.point
            self.logger.debug(f"📊 Symbol Point: {point}")
            self.logger.debug(f"📊 Bid: {tick.bid:.5f}, Ask: {tick.ask:.5f}")
            
            if signal_type == 'BUY':
                price = tick.ask
                order_type = mt5.ORDER_TYPE_BUY
                # Gold için point hesaplama (XAUUSD point = 0.01)
                sl = price - (self.stop_loss_pips * 0.1)   # 8 pip = 0.8 
                tp = price + (self.take_profit_pips * 0.1)  # 3 pip = 0.3
            else:  # SELL
                price = tick.bid
                order_type = mt5.ORDER_TYPE_SELL
                sl = price + (self.stop_loss_pips * 0.1)
                tp = price - (self.take_profit_pips * 0.1)
            
            self.logger.info(f"🎯 {signal_type} EMİR HAZIR:")
            self.logger.info(f"   💰 Price: {price:.5f}")
            self.logger.info(f"   🛑 Stop Loss: {sl:.5f}")
            self.logger.info(f"   🎯 Take Profit: {tp:.5f}")
            
            # Emir gönder
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": self.lot_size,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 50,  # Daha büyük sapma toleransı
                "magic": self.magic_number,
                "comment": "DebugScalping",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            self.logger.debug(f"📤 Emir gönderiliyor: {request}")
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"🚀 {signal_type} EMİR BAŞARILI!")
                self.logger.info(f"   📝 Ticket: {result.order}")
                self.logger.info(f"   💰 Volume: {result.volume}")
                self.logger.info(f"   💵 Price: {result.price:.5f}")
                return True
            else:
                self.logger.error(f"❌ Emir BAŞARISIZ!")
                self.logger.error(f"   🔢 Retcode: {result.retcode}")
                self.logger.error(f"   📝 Comment: {result.comment if hasattr(result, 'comment') else 'N/A'}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Emir hatası: {e}")
            return False
    
    def run_debug_scalping(self):
        """Debug scalping döngüsü"""
        self.logger.info("🔥 DEBUG Scalping Bot başlatıldı!")
        self.logger.info(f"📊 Symbol: {self.symbol}")
        self.logger.info(f"📊 Timeframe: M1")
        self.logger.info(f"🎯 TP: {self.take_profit_pips} pip, SL: {self.stop_loss_pips} pip")
        self.logger.info(f"📈 EMA: {self.ema_fast}/{self.ema_slow}")
        
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                self.logger.info(f"\n--- DÖNGÜ {loop_count} ---")
                
                # Account bilgisi
                account = mt5.account_info()
                if account:
                    self.logger.debug(f"💼 Hesap: Balance={account.balance:.2f}, Equity={account.equity:.2f}")
                
                # Veri al
                df = self.get_data()
                if df is None:
                    time.sleep(5)
                    continue
                
                # Pozisyon durumu
                current_positions = self.count_positions()
                
                # Sinyal üret
                signal = self.generate_simple_signal(df)
                if signal is None:
                    self.logger.debug("⏳ Sinyal bekleniyor...")
                    time.sleep(3)
                    continue
                
                # Emir ver
                self.logger.info(f"🎯 {signal['signal']} SİNYALİ TESPİT EDİLDİ!")
                if self.place_order(signal['signal']):
                    self.logger.info(f"✅ {signal['signal']} işlemi başarıyla açıldı!")
                    time.sleep(5)  # Başarılı işlem sonrası kısa bekle
                else:
                    self.logger.warning(f"⚠️ {signal['signal']} işlemi açılamadı!")
                
                time.sleep(1)  # Çok hızlı döngü (1 saniye)
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Bot kullanıcı tarafından durduruldu.")
        except Exception as e:
            self.logger.error(f"❌ Bot hatası: {e}")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    # DEBUG SCALPING BOT
    bot = DebugScalpingBot(
        symbol="XAUUSD",  # + işareti olmadan dene
        timeframe=mt5.TIMEFRAME_M1
    )
    
    print("🔧 DEBUG MOD AYARLARI:")
    print(f"🎯 Take Profit: {bot.take_profit_pips} pip")
    print(f"🛑 Stop Loss: {bot.stop_loss_pips} pip") 
    print(f"📈 EMA Fast: {bot.ema_fast}, Slow: {bot.ema_slow}")
    print(f"💼 Max Pozisyon: {bot.max_positions}")
    print(f"💰 Lot Size: {bot.lot_size}")
    print(f"📊 Symbol: {bot.symbol}")
    print("\n🚀 Bot başlatılıyor (Ctrl+C ile durdur)...")
    
    bot.run_debug_scalping()