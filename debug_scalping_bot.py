import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
import talib

# Detaylı debug logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

class DebuggingScalpingBot:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M1):
        self.symbol = symbol
        self.timeframe = timeframe
        self.magic_number = 77777
        
        # Daha agresif ayarlar - test için
        self.lot_size = 0.01
        self.take_profit_pips = 3      # TP'yi düşürdük
        self.stop_loss_pips = 2        # SL'yi düşürdük
        self.max_positions = 2
        
        # Daha hassas parametreler
        self.ema_fast = 5              # Daha hızlı
        self.ema_slow = 13             # Daha hızlı
        self.min_trend_strength = 0.1  # Daha düşük eşik
        
        # Daha esnek filtreler
        self.min_price_move = 0.05     # Çok düşük (0.5 pip)
        self.max_spread = 3.0          # Daha yüksek spread toleransı
        self.volatility_filter = False # Volatilite filtresini kapat
        
        self.quick_profit_pips = 2
        self.trail_stop = False
        
        self.logger = logging.getLogger(__name__)
        self.last_signal_time = None
        self.winning_streak = 0
        self.losing_streak = 0
        
        # Debug sayaçları
        self.debug_stats = {
            'market_checks': 0,
            'failed_market_checks': 0,
            'data_fetches': 0,
            'failed_data_fetches': 0,
            'signal_attempts': 0,
            'signals_generated': 0,
            'order_attempts': 0,
            'successful_orders': 0
        }
        
        self.initialize_mt5()
    
    def debug_print_stats(self):
        """Debug istatistiklerini yazdır"""
        self.logger.info("=" * 50)
        self.logger.info("📊 DEBUG İSTATİSTİKLER:")
        for key, value in self.debug_stats.items():
            self.logger.info(f"   {key}: {value}")
        self.logger.info("=" * 50)
    
    def initialize_mt5(self):
        """MT5 başlat - debug version"""
        self.logger.info("🔧 MT5 başlatılıyor...")
        
        if not mt5.initialize():
            self.logger.error("❌ MT5 başlatılamadı!")
            return False
        
        self.logger.info("✅ MT5 başarıyla başlatıldı")
        
        # Symbol variants - daha geniş arama
        variants = [self.symbol, self.symbol + "+", "XAUUSD.", "GOLD", "XAU/USD", "XAUUSD.m"]
        found_symbol = False
        
        for variant in variants:
            self.logger.debug(f"🔍 Symbol test ediliyor: {variant}")
            if mt5.symbol_select(variant, True):
                self.symbol = variant
                self.logger.info(f"✅ Symbol bulundu ve aktif edildi: {self.symbol}")
                found_symbol = True
                break
            else:
                self.logger.debug(f"❌ Symbol bulunamadı: {variant}")
        
        if not found_symbol:
            self.logger.error("❌ Hiçbir symbol bulunamadı!")
            # Mevcut symbolları listele
            symbols = mt5.symbols_get()
            if symbols:
                self.logger.info("📋 Mevcut symbollar:")
                for i, sym in enumerate(symbols[:10]):  # İlk 10'u göster
                    self.logger.info(f"   {i+1}. {sym.name}")
            return False
        
        # Symbol bilgilerini kontrol et
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info:
            self.logger.info(f"📊 Symbol bilgileri:")
            self.logger.info(f"   Spread: {symbol_info.spread}")
            self.logger.info(f"   Digits: {symbol_info.digits}")
            self.logger.info(f"   Trade mode: {symbol_info.trade_mode}")
            self.logger.info(f"   Min lot: {symbol_info.volume_min}")
            self.logger.info(f"   Max lot: {symbol_info.volume_max}")
        
        return True
    
    def get_data(self, bars=50):
        """Market verisi al - debug version"""
        self.debug_stats['data_fetches'] += 1
        self.logger.debug(f"📈 Veri alınıyor: {bars} bar")
        
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None:
            self.debug_stats['failed_data_fetches'] += 1
            self.logger.error(f"❌ Veri alınamadı: {mt5.last_error()}")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        self.logger.debug(f"✅ {len(df)} bar alındı. Son fiyat: {df['close'].iloc[-1]:.5f}")
        return df
    
    def check_market_conditions(self):
        """Market koşulları - debug version"""
        self.debug_stats['market_checks'] += 1
        
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            self.debug_stats['failed_market_checks'] += 1
            self.logger.debug(f"❌ Tick verisi alınamadı: {mt5.last_error()}")
            return False
        
        # Spread kontrolü
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info:
            if symbol_info.digits >= 3:  # XAUUSD gibi
                pip_value = 0.1
            else:
                pip_value = 0.0001
                
            spread_pips = (tick.ask - tick.bid) / pip_value
        else:
            spread_pips = (tick.ask - tick.bid) * 10  # Fallback
        
        self.logger.debug(f"📊 Market durumu:")
        self.logger.debug(f"   Bid: {tick.bid:.5f}, Ask: {tick.ask:.5f}")
        self.logger.debug(f"   Spread: {spread_pips:.2f} pips")
        
        if spread_pips > self.max_spread:
            self.debug_stats['failed_market_checks'] += 1
            self.logger.debug(f"❌ Spread çok yüksek: {spread_pips:.2f} > {self.max_spread}")
            return False
        
        # Volatilite kontrolü (eğer aktifse)
        if self.volatility_filter:
            df = self.get_data(20)
            if df is None:
                self.debug_stats['failed_market_checks'] += 1
                return False
            
            price_range = df['high'].max() - df['low'].min()
            self.logger.debug(f"   Volatilite: {price_range:.5f}")
            
            if price_range < 1.0:  # Daha düşük eşik
                self.debug_stats['failed_market_checks'] += 1
                self.logger.debug(f"❌ Volatilite düşük: {price_range:.5f}")
                return False
        
        self.logger.debug("✅ Market koşulları uygun")
        return True
    
    def calculate_trend_strength(self, df):
        """Trend gücü - debug version"""
        if len(df) < self.ema_slow:
            self.logger.debug(f"❌ Yetersiz veri: {len(df)} < {self.ema_slow}")
            return 0
        
        try:
            ema_fast = talib.EMA(df['close'].values, timeperiod=self.ema_fast)
            ema_slow = talib.EMA(df['close'].values, timeperiod=self.ema_slow)
            
            if len(ema_fast) < 10:
                self.logger.debug(f"❌ Yetersiz EMA verisi: {len(ema_fast)}")
                return 0
            
            # Son 5 barın trend tutarlılığı (daha kısa)
            fast_slope = np.polyfit(range(5), ema_fast[-5:], 1)[0]
            slow_slope = np.polyfit(range(5), ema_slow[-5:], 1)[0]
            
            self.logger.debug(f"📈 EMA eğimleri - Fast: {fast_slope:.6f}, Slow: {slow_slope:.6f}")
            
            if fast_slope > 0 and slow_slope > 0:
                trend_strength = abs(fast_slope + slow_slope)
                self.logger.debug(f"🟢 Bullish trend gücü: {trend_strength:.6f}")
                return trend_strength
            elif fast_slope < 0 and slow_slope < 0:
                trend_strength = -abs(fast_slope + slow_slope)
                self.logger.debug(f"🔴 Bearish trend gücü: {trend_strength:.6f}")
                return trend_strength
            else:
                self.logger.debug("🟡 Karışık trend")
                return 0
                
        except Exception as e:
            self.logger.error(f"❌ Trend hesaplama hatası: {e}")
            return 0
    
    def generate_smart_signal(self, df):
        """Sinyal üretimi - debug version"""
        self.debug_stats['signal_attempts'] += 1
        
        if len(df) < self.ema_slow:
            self.logger.debug(f"❌ Sinyal için yetersiz veri: {len(df)} < {self.ema_slow}")
            return None
        
        try:
            # EMA hesapla
            ema_fast = talib.EMA(df['close'].values, timeperiod=self.ema_fast)
            ema_slow = talib.EMA(df['close'].values, timeperiod=self.ema_slow)
            
            if len(ema_fast) < 2:
                self.logger.debug("❌ EMA hesaplanamadı")
                return None
            
            current_price = df['close'].iloc[-1]
            prev_price = df['close'].iloc[-2]
            current_fast = ema_fast[-1]
            current_slow = ema_slow[-1]
            prev_fast = ema_fast[-2]
            prev_slow = ema_slow[-2]
            
            self.logger.debug(f"💹 Fiyat bilgileri:")
            self.logger.debug(f"   Current: {current_price:.5f}, Previous: {prev_price:.5f}")
            self.logger.debug(f"   EMA Fast: {current_fast:.5f} (önceki: {prev_fast:.5f})")
            self.logger.debug(f"   EMA Slow: {current_slow:.5f} (önceki: {prev_slow:.5f})")
            
            # Fiyat hareketi kontrolü
            price_move = abs(current_price - prev_price)
            self.logger.debug(f"   Fiyat hareketi: {price_move:.5f} (min: {self.min_price_move})")
            
            if price_move < self.min_price_move:
                self.logger.debug(f"❌ Fiyat hareketi yetersiz: {price_move:.5f}")
                return None
            
            # Trend gücü kontrolü
            trend_strength = self.calculate_trend_strength(df)
            self.logger.debug(f"   Trend gücü: {trend_strength:.6f} (min: {self.min_trend_strength})")
            
            signal = None
            confidence = 0
            
            # 1. EMA CROSSOVER kontrolü
            if prev_fast <= prev_slow and current_fast > current_slow:
                signal = "BUY"
                confidence = 3
                self.logger.info(f"🟢 EMA CROSSOVER BUY sinyali!")
                
            elif prev_fast >= prev_slow and current_fast < current_slow:
                signal = "SELL"
                confidence = 3
                self.logger.info(f"🔴 EMA CROSSOVER SELL sinyali!")
            
            # 2. Daha basit trend takip
            elif abs(trend_strength) >= self.min_trend_strength:
                if current_fast > current_slow and current_price > current_fast:
                    signal = "BUY"
                    confidence = 2
                    self.logger.info(f"🟢 TREND BUY sinyali!")
                    
                elif current_fast < current_slow and current_price < current_fast:
                    signal = "SELL"
                    confidence = 2
                    self.logger.info(f"🔴 TREND SELL sinyali!")
            
            # 3. Basit momentum sinyali (daha agresif)
            else:
                price_momentum = current_price - prev_price
                ema_momentum = current_fast - prev_fast
                
                if price_momentum > 0 and ema_momentum > 0 and current_fast > current_slow:
                    signal = "BUY"
                    confidence = 1
                    self.logger.info(f"🟢 MOMENTUM BUY sinyali!")
                    
                elif price_momentum < 0 and ema_momentum < 0 and current_fast < current_slow:
                    signal = "SELL"
                    confidence = 1
                    self.logger.info(f"🔴 MOMENTUM SELL sinyali!")
            
            if signal:
                self.debug_stats['signals_generated'] += 1
                return {
                    'signal': signal,
                    'confidence': confidence,
                    'price': current_price,
                    'trend_strength': trend_strength,
                    'ema_fast': current_fast,
                    'ema_slow': current_slow
                }
            else:
                self.logger.debug("❌ Sinyal üretilemedi")
                return None
                
        except Exception as e:
            self.logger.error(f"❌ Sinyal üretim hatası: {e}")
            return None
    
    def count_positions(self):
        """Pozisyon sayısı"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return 0
        
        my_positions = [p for p in positions if p.magic == self.magic_number]
        self.logger.debug(f"📊 Aktif pozisyon sayısı: {len(my_positions)}")
        return len(my_positions)
    
    def place_smart_order(self, signal_data):
        """Emir yerleştirme - debug version"""
        self.debug_stats['order_attempts'] += 1
        
        try:
            current_positions = self.count_positions()
            if current_positions >= self.max_positions:
                self.logger.debug(f"❌ Max pozisyon sınırı: {current_positions} >= {self.max_positions}")
                return False
            
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                self.logger.error(f"❌ Tick verisi alınamadı: {mt5.last_error()}")
                return False
            
            signal_type = signal_data['signal']
            confidence = signal_data['confidence']
            
            # Symbol info al
            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                self.logger.error("❌ Symbol bilgisi alınamadı")
                return False
            
            # Pip değerini hesapla
            if symbol_info.digits >= 3:  # XAUUSD gibi
                pip_value = 0.1
            else:
                pip_value = 0.0001
            
            self.logger.info(f"🚀 {signal_type} EMİR HAZİRLANIYOR...")
            self.logger.info(f"   💰 Confidence: {confidence}")
            self.logger.info(f"   📊 Pip değeri: {pip_value}")
            
            if signal_type == 'BUY':
                price = tick.ask
                sl = price - (self.stop_loss_pips * pip_value)
                tp = price + (self.take_profit_pips * pip_value)
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price = tick.bid
                sl = price + (self.stop_loss_pips * pip_value)
                tp = price - (self.take_profit_pips * pip_value)
                order_type = mt5.ORDER_TYPE_SELL
            
            # Lot size kontrolü
            if self.lot_size < symbol_info.volume_min:
                adjusted_lot = symbol_info.volume_min
                self.logger.warning(f"⚠️ Lot size artırıldı: {self.lot_size} -> {adjusted_lot}")
            else:
                adjusted_lot = self.lot_size
            
            self.logger.info(f"📋 Emir detayları:")
            self.logger.info(f"   Tip: {signal_type}")
            self.logger.info(f"   Fiyat: {price:.5f}")
            self.logger.info(f"   SL: {sl:.5f}")
            self.logger.info(f"   TP: {tp:.5f}")
            self.logger.info(f"   Lot: {adjusted_lot}")
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": adjusted_lot,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 50,  # Daha yüksek deviation
                "magic": self.magic_number,
                "comment": f"Debug_{confidence}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            self.logger.info("📤 Emir gönderiliyor...")
            result = mt5.order_send(request)
            
            self.logger.info(f"📥 Emir sonucu:")
            self.logger.info(f"   Retcode: {result.retcode}")
            self.logger.info(f"   Deal: {result.deal}")
            self.logger.info(f"   Order: {result.order}")
            self.logger.info(f"   Comment: {result.comment}")
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.debug_stats['successful_orders'] += 1
                self.logger.info(f"✅ {signal_type} EMİR BAŞARILI!")
                return True
            else:
                self.logger.error(f"❌ Emir başarısız - Retcode: {result.retcode}")
                self.logger.error(f"   Hata: {result.comment}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Emir hatası: {e}")
            return False
    
    def run_debug_scalping(self):
        """Debug scalping döngüsü"""
        self.logger.info("🐛 DEBUG SCALPING BOT BAŞLATILDI!")
        self.logger.info(f"📊 Symbol: {self.symbol}")
        self.logger.info(f"🎯 TP/SL: {self.take_profit_pips}/{self.stop_loss_pips} pip")
        self.logger.info(f"📈 EMA: {self.ema_fast}/{self.ema_slow}")
        self.logger.info(f"🔧 Min trend: {self.min_trend_strength}")
        self.logger.info(f"🔧 Min move: {self.min_price_move}")
        self.logger.info(f"🔧 Max spread: {self.max_spread}")
        
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                self.logger.info(f"\n🔄 DÖNGÜ #{loop_count}")
                
                # Market koşulları kontrolü
                if not self.check_market_conditions():
                    self.logger.debug("⏳ Market koşulları uygun değil, bekleniyor...")
                    time.sleep(5)
                    continue
                
                # Veri al
                df = self.get_data()
                if df is None:
                    self.logger.debug("⏳ Veri alınamadı, bekleniyor...")
                    time.sleep(5)
                    continue
                
                # Sinyal üret
                signal = self.generate_smart_signal(df)
                if signal is None:
                    self.logger.debug("⏳ Sinyal yok, bekleniyor...")
                    time.sleep(3)
                    continue
                
                # Emir ver
                self.logger.info(f"🎯 SİNYAL BULUNDU: {signal['signal']} (Güven: {signal['confidence']})")
                if self.place_smart_order(signal):
                    self.logger.info("🎉 İŞLEM AÇILDI!")
                    time.sleep(10)  # Başarılı emirden sonra bekle
                else:
                    self.logger.warning("⚠️ Emir açılamadı")
                
                # Her 10 döngüde istatistik
                if loop_count % 10 == 0:
                    self.debug_print_stats()
                
                time.sleep(1)  # Hızlı döngü
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Bot durduruldu.")
            self.debug_print_stats()
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    bot = DebuggingScalpingBot(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M1
    )
    
    print("🐛 DEBUG SCALPING BOT - PROBLEM TESPİT MODU")
    print("Bu versiyon her adımı detaylı loglar.")
    print("Neden işlem açmadığını görebilirsiniz.")
    print("\n🚀 Test başlatılıyor... (Ctrl+C ile durdur)")
    
    bot.run_debug_scalping()