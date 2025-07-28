import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
import talib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class ProfitableScalpingBot:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M1):
        self.symbol = symbol
        self.timeframe = timeframe
        self.magic_number = 77777
        
        # 🎯 KARLILIĞI ARTIRAN AYARLAR
        self.lot_size = 0.01
        self.take_profit_pips = 6      # 6 pip TP (artırdık)
        self.stop_loss_pips = 4        # 4 pip SL (düşürdük) → 1:1.5 R/R
        self.max_positions = 2         # Düşük pozisyon (risk azaltma)
        
        # 📈 TREND TAKİP PARAMETRELERİ
        self.ema_fast = 8              # Biraz yavaşlattık
        self.ema_slow = 21             # Fibonacci sayısı
        self.min_trend_strength = 0.3  # Minimum trend gücü
        
        # 🛡️ GÜVENLİK FİLTRELERİ
        self.min_price_move = 0.2      # En az 2 pip hareket
        self.max_spread = 1.5          # Max 1.5 pip spread
        self.volatility_filter = True  # Volatilite filtresi
        
        # 💰 HIZLI KAR ALMA
        self.quick_profit_pips = 3     # 3 pip'te hızlı kapat
        self.trail_stop = True         # Trailing stop
        
        self.logger = logging.getLogger(__name__)
        self.last_signal_time = None
        self.winning_streak = 0
        self.losing_streak = 0
        
        self.initialize_mt5()
    
    def initialize_mt5(self):
        """MT5 başlat"""
        if not mt5.initialize():
            self.logger.error("MT5 başlatılamadı!")
            return False
        
        # Symbol variants
        variants = [self.symbol, self.symbol + "+", "XAUUSD.", "GOLD"]
        for variant in variants:
            if mt5.symbol_select(variant, True):
                self.symbol = variant
                self.logger.info(f"✅ {self.symbol} aktif!")
                break
        else:
            self.logger.error("Symbol bulunamadı!")
            return False
        
        return True
    
    def get_data(self, bars=50):
        """Market verisi al"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    def check_market_conditions(self):
        """Market koşulları uygun mu?"""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return False
        
        # Spread kontrolü
        spread_pips = (tick.ask - tick.bid) * 100  # XAUUSD için
        if spread_pips > self.max_spread:
            self.logger.debug(f"Spread çok yüksek: {spread_pips:.1f} pips")
            return False
        
        # Volatilite kontrolü
        if self.volatility_filter:
            df = self.get_data(20)
            if df is None:
                return False
            
            # Son 20 bardaki fiyat aralığı
            price_range = df['high'].max() - df['low'].min()
            if price_range < 2.0:  # En az 2 dolar hareket
                self.logger.debug(f"Volatilite düşük: {price_range:.2f}")
                return False
        
        return True
    
    def calculate_trend_strength(self, df):
        """Trend gücünü hesapla"""
        if len(df) < self.ema_slow:
            return 0
        
        ema_fast = talib.EMA(df['close'].values, timeperiod=self.ema_fast)
        ema_slow = talib.EMA(df['close'].values, timeperiod=self.ema_slow)
        
        if len(ema_fast) < 10:
            return 0
        
        # Son 10 barın trend tutarlılığı
        fast_slope = np.polyfit(range(10), ema_fast[-10:], 1)[0]
        slow_slope = np.polyfit(range(10), ema_slow[-10:], 1)[0]
        
        # Aynı yönde eğim = güçlü trend
        if fast_slope > 0 and slow_slope > 0:
            return abs(fast_slope + slow_slope)  # Bullish trend gücü
        elif fast_slope < 0 and slow_slope < 0:
            return -abs(fast_slope + slow_slope)  # Bearish trend gücü
        else:
            return 0  # Belirsiz trend
    
    def generate_smart_signal(self, df):
        """AKILLI ve KARLI sinyal üretimi"""
        if len(df) < self.ema_slow:
            return None
        
        # EMA hesapla
        ema_fast = talib.EMA(df['close'].values, timeperiod=self.ema_fast)
        ema_slow = talib.EMA(df['close'].values, timeperiod=self.ema_slow)
        
        if len(ema_fast) < 2:
            return None
        
        current_price = df['close'].iloc[-1]
        prev_price = df['close'].iloc[-2]
        current_fast = ema_fast[-1]
        current_slow = ema_slow[-1]
        prev_fast = ema_fast[-2]
        prev_slow = ema_slow[-2]
        
        # Fiyat hareketi kontrolü
        price_move = abs(current_price - prev_price)
        if price_move < self.min_price_move:
            self.logger.debug(f"Fiyat hareketi yetersiz: {price_move:.3f}")
            return None
        
        # Trend gücü kontrolü
        trend_strength = self.calculate_trend_strength(df)
        if abs(trend_strength) < self.min_trend_strength:
            self.logger.debug(f"Trend gücü yetersiz: {trend_strength:.3f}")
            return None
        
        signal = None
        confidence = 0
        
        # 1. GÜÇLÜ EMA CROSSOVER (En güvenilir)
        if prev_fast <= prev_slow and current_fast > current_slow:
            signal = "BUY"
            confidence = 3
            self.logger.info(f"🟢 GÜÇLÜ BUY: EMA Crossover + Trend({trend_strength:.3f})")
            
        elif prev_fast >= prev_slow and current_fast < current_slow:
            signal = "SELL"
            confidence = 3
            self.logger.info(f"🔴 GÜÇLÜ SELL: EMA Crossover + Trend({trend_strength:.3f})")
        
        # 2. TREND YÖNÜNDEKİ PULLBACK'LER (Yüksek kazanç)
        elif trend_strength > self.min_trend_strength:
            # Bullish trend'de düşüş = BUY fırsatı
            if (current_price < current_fast < current_slow and 
                prev_price > prev_fast and 
                price_move > self.min_price_move):
                signal = "BUY"
                confidence = 2
                self.logger.info(f"🟢 PULLBACK BUY: Trend gücü {trend_strength:.3f}")
                
        elif trend_strength < -self.min_trend_strength:
            # Bearish trend'de yükseliş = SELL fırsatı
            if (current_price > current_fast > current_slow and 
                prev_price < prev_fast and 
                price_move > self.min_price_move):
                signal = "SELL"
                confidence = 2
                self.logger.info(f"🔴 PULLBACK SELL: Trend gücü {trend_strength:.3f}")
        
        # Kazanma serisi kontrolü (güven artırma)
        if self.winning_streak >= 2:
            confidence += 1
        elif self.losing_streak >= 2:
            confidence -= 1
        
        if signal and confidence >= 2:
            return {
                'signal': signal,
                'confidence': confidence,
                'price': current_price,
                'trend_strength': trend_strength,
                'ema_fast': current_fast,
                'ema_slow': current_slow
            }
        
        return None
    
    def count_positions(self):
        """Pozisyon sayısı"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return 0
        return len([p for p in positions if p.magic == self.magic_number])
    
    def place_smart_order(self, signal_data):
        """AKILLI emir yerleştirme"""
        try:
            if self.count_positions() >= self.max_positions:
                return False
            
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return False
            
            signal_type = signal_data['signal']
            confidence = signal_data['confidence']
            
            # Güven seviyesine göre lot size ayarla
            lot_multiplier = min(confidence / 2.0, 1.5)  # Max 1.5x
            adjusted_lot = self.lot_size * lot_multiplier
            adjusted_lot = round(adjusted_lot, 2)
            
            if signal_type == 'BUY':
                price = tick.ask
                # DAHA İYİ R/R için dinamik SL/TP
                sl = price - (self.stop_loss_pips * 0.1)
                tp = price + (self.take_profit_pips * 0.1)
                order_type = mt5.ORDER_TYPE_BUY
            else:
                price = tick.bid
                sl = price + (self.stop_loss_pips * 0.1)
                tp = price - (self.take_profit_pips * 0.1)
                order_type = mt5.ORDER_TYPE_SELL
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": adjusted_lot,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 30,
                "magic": self.magic_number,
                "comment": f"Smart_{confidence}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"🚀 {signal_type} EMİR AÇILDI!")
                self.logger.info(f"   💰 Lot: {adjusted_lot} (Güven: {confidence})")
                self.logger.info(f"   📊 Price: {price:.2f}, SL: {sl:.2f}, TP: {tp:.2f}")
                self.logger.info(f"   📈 R/R: 1:{self.take_profit_pips/self.stop_loss_pips:.1f}")
                return True
            else:
                self.logger.error(f"❌ Emir başarısız: {result.retcode}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Emir hatası: {e}")
            return False
    
    def manage_positions(self):
        """Pozisyon yönetimi - HIZLI KAR ALMA"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if not positions:
                return
            
            for pos in positions:
                if pos.magic != self.magic_number:
                    continue
                
                # Hızlı kar alma (3 pip)
                current_profit_pips = pos.profit / (pos.volume * 10)  # Yaklaşık pip hesabı
                
                if current_profit_pips >= self.quick_profit_pips:
                    self.close_position(pos.ticket, "Hızlı kar alma")
                    self.winning_streak += 1
                    self.losing_streak = 0
                    self.logger.info(f"💰 Hızlı kar alındı: {current_profit_pips:.1f} pip")
                
                # Trailing stop (isteğe bağlı)
                elif self.trail_stop and current_profit_pips >= 2:
                    # 2 pip karda trailing stop aktif et
                    pass  # Basit versiyon için skip
                    
        except Exception as e:
            self.logger.error(f"Pozisyon yönetimi hatası: {e}")
    
    def close_position(self, ticket, reason=""):
        """Pozisyon kapat"""
        try:
            positions = mt5.positions_get(ticket=ticket)
            if not positions:
                return False
            
            pos = positions[0]
            tick = mt5.symbol_info_tick(self.symbol)
            
            if pos.type == mt5.POSITION_TYPE_BUY:
                price = tick.bid
                order_type = mt5.ORDER_TYPE_SELL
            else:
                price = tick.ask
                order_type = mt5.ORDER_TYPE_BUY
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 30,
                "magic": self.magic_number,
                "comment": reason,
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            return result.retcode == mt5.TRADE_RETCODE_DONE
            
        except Exception as e:
            self.logger.error(f"Pozisyon kapatma hatası: {e}")
            return False
    
    def run_profitable_scalping(self):
        """KARLI scalping döngüsü"""
        self.logger.info("💰 KARLI SCALPING BOT BAŞLATILDI!")
        self.logger.info(f"📊 Symbol: {self.symbol}")
        self.logger.info(f"🎯 R/R: 1:{self.take_profit_pips/self.stop_loss_pips:.1f}")
        self.logger.info(f"⚡ Hızlı kar: {self.quick_profit_pips} pip")
        self.logger.info(f"📈 EMA: {self.ema_fast}/{self.ema_slow}")
        
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                
                # Market koşulları kontrolü
                if not self.check_market_conditions():
                    time.sleep(10)
                    continue
                
                # Pozisyon yönetimi (hızlı kar alma)
                self.manage_positions()
                
                # Veri al
                df = self.get_data()
                if df is None:
                    time.sleep(5)
                    continue
                
                # Akıllı sinyal üret
                signal = self.generate_smart_signal(df)
                if signal is None:
                    time.sleep(3)
                    continue
                
                # Emir ver
                if self.place_smart_order(signal):
                    self.logger.info(f"✅ İşlem açıldı! Güven: {signal['confidence']}")
                    time.sleep(5)
                
                # Her 50 döngüde durum raporu
                if loop_count % 50 == 0:
                    account = mt5.account_info()
                    if account:
                        self.logger.info(f"📊 Hesap durumu: Balance={account.balance:.2f}, "
                                       f"Equity={account.equity:.2f}")
                        self.logger.info(f"🏆 Seri: Kazanma={self.winning_streak}, "
                                       f"Kaybetme={self.losing_streak}")
                
                time.sleep(2)  # 2 saniye döngü
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Bot durduruldu.")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    bot = ProfitableScalpingBot(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M1
    )
    
    print("💰 KARLI SCALPING BOT AYARLARI:")
    print(f"🎯 Take Profit: {bot.take_profit_pips} pip")
    print(f"🛑 Stop Loss: {bot.stop_loss_pips} pip")
    print(f"📊 Risk/Reward: 1:{bot.take_profit_pips/bot.stop_loss_pips:.1f}")
    print(f"⚡ Hızlı kar alma: {bot.quick_profit_pips} pip")
    print(f"📈 EMA Trend: {bot.ema_fast}/{bot.ema_slow}")
    print(f"🛡️ Max Spread: {bot.max_spread} pip")
    print(f"💼 Max Pozisyon: {bot.max_positions}")
    print("\n🚀 Para kazanmaya başlayalım! (Ctrl+C ile durdur)")
    
    bot.run_profitable_scalping()