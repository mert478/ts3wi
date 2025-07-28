import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
import talib

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class ImprovedScalpingBot:
    def __init__(self, symbol="XAUUSD", timeframe=mt5.TIMEFRAME_M1):
        self.symbol = symbol
        self.timeframe = timeframe
        self.magic_number = 77777
        
        # 🎯 DÜZELTİLMİŞ AYARLAR
        self.lot_size = 0.01
        self.take_profit_pips = 4      
        self.stop_loss_pips = 3        
        self.max_positions = 3         
        
        # 📈 DAHA ETKİN TREND PARAMETRELERİ
        self.ema_fast = 9              
        self.ema_slow = 21             
        self.min_trend_strength = 0.05  # ÇOK DÜŞÜK EŞIK
        
        # 🛡️ ESNEKLEŞTİRİLMİŞ FİLTRELER
        self.min_price_move = 0.02      # Çok düşük (0.2 pip)
        self.max_spread = 4.0           # Yüksek spread toleransı
        self.volatility_filter = False  # Kapalı
        
        # 💰 HIZLI İŞLEM AYARLARI
        self.quick_profit_pips = 2     
        self.trail_stop = False
        
        # ⚡ SINYAL ÇEŞİTLİLİĞİ
        self.use_rsi = True
        self.use_macd = True
        self.rsi_oversold = 30
        self.rsi_overbought = 70
        
        self.logger = logging.getLogger(__name__)
        self.last_signal_time = None
        self.winning_streak = 0
        self.losing_streak = 0
        self.total_signals = 0
        self.successful_trades = 0
        
        self.initialize_mt5()
    
    def initialize_mt5(self):
        """Geliştirilmiş MT5 başlatma"""
        if not mt5.initialize():
            self.logger.error("MT5 başlatılamadı!")
            return False
        
        # Daha kapsamlı symbol arama
        variants = [
            self.symbol, 
            self.symbol + "+", 
            "XAUUSD.", 
            "GOLD", 
            "XAU/USD",
            "XAUUSD.m",
            "XAUUSD_",
            "#GOLD"
        ]
        
        for variant in variants:
            if mt5.symbol_select(variant, True):
                self.symbol = variant
                self.logger.info(f"✅ Symbol aktif: {self.symbol}")
                
                # Symbol bilgilerini logla
                info = mt5.symbol_info(self.symbol)
                if info:
                    self.logger.info(f"📊 Spread: {info.spread}, Digits: {info.digits}")
                    self.logger.info(f"📊 Min/Max lot: {info.volume_min}/{info.volume_max}")
                break
        else:
            self.logger.error("Symbol bulunamadı!")
            return False
        
        return True
    
    def get_data(self, bars=100):  # Daha fazla veri
        """Geliştirilmiş veri alma"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None:
            self.logger.error(f"Veri alınamadı: {mt5.last_error()}")
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        
        # Temel teknik analiz hesaplamaları
        try:
            df['ema_fast'] = talib.EMA(df['close'].values, timeperiod=self.ema_fast)
            df['ema_slow'] = talib.EMA(df['close'].values, timeperiod=self.ema_slow)
            
            if self.use_rsi:
                df['rsi'] = talib.RSI(df['close'].values, timeperiod=14)
            
            if self.use_macd:
                macd, macd_signal, macd_hist = talib.MACD(df['close'].values)
                df['macd'] = macd
                df['macd_signal'] = macd_signal
                df['macd_hist'] = macd_hist
                
        except Exception as e:
            self.logger.warning(f"Teknik analiz hesaplama hatası: {e}")
        
        return df
    
    def check_market_conditions(self):
        """Esnek market koşul kontrolü"""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return False
        
        # Sadece spread kontrolü (çok esnek)
        symbol_info = mt5.symbol_info(self.symbol)
        if symbol_info:
            if symbol_info.digits >= 3:
                pip_value = 0.1
            else:
                pip_value = 0.0001
            spread_pips = (tick.ask - tick.bid) / pip_value
        else:
            spread_pips = (tick.ask - tick.bid) * 10
        
        if spread_pips > self.max_spread:
            return False
        
        # Market saatleri kontrolü (isteğe bağlı)
        now = datetime.now()
        hour = now.hour
        
        # Asya, Avrupa, Amerika oturumları
        if hour in [0, 1, 2, 3, 4, 5, 22, 23]:  # Düşük volatilite saatleri
            return True  # Yine de kabul et
        
        return True
    
    def generate_multiple_signals(self, df):
        """Çoklu sinyal sistemi"""
        if len(df) < max(self.ema_slow, 20):
            return None
        
        signals = []
        
        # 1. EMA CROSSOVER SİNYALİ
        ema_signal = self.get_ema_signal(df)
        if ema_signal:
            signals.append(ema_signal)
        
        # 2. RSI SİNYALİ (eğer aktifse)
        if self.use_rsi and 'rsi' in df.columns:
            rsi_signal = self.get_rsi_signal(df)
            if rsi_signal:
                signals.append(rsi_signal)
        
        # 3. MACD SİNYALİ (eğer aktifse)
        if self.use_macd and 'macd' in df.columns:
            macd_signal = self.get_macd_signal(df)
            if macd_signal:
                signals.append(macd_signal)
        
        # 4. FİYAT AKSİYONU SİNYALİ
        price_action_signal = self.get_price_action_signal(df)
        if price_action_signal:
            signals.append(price_action_signal)
        
        # En güçlü sinyali seç
        if signals:
            best_signal = max(signals, key=lambda x: x['confidence'])
            self.total_signals += 1
            return best_signal
        
        return None
    
    def get_ema_signal(self, df):
        """EMA crossover sinyali"""
        try:
            current_fast = df['ema_fast'].iloc[-1]
            current_slow = df['ema_slow'].iloc[-1]
            prev_fast = df['ema_fast'].iloc[-2]
            prev_slow = df['ema_slow'].iloc[-2]
            
            if pd.isna(current_fast) or pd.isna(current_slow):
                return None
            
            # Golden Cross (Bullish)
            if prev_fast <= prev_slow and current_fast > current_slow:
                return {
                    'signal': 'BUY',
                    'confidence': 3,
                    'type': 'EMA_CROSS',
                    'price': df['close'].iloc[-1]
                }
            
            # Death Cross (Bearish)
            elif prev_fast >= prev_slow and current_fast < current_slow:
                return {
                    'signal': 'SELL',
                    'confidence': 3,
                    'type': 'EMA_CROSS',
                    'price': df['close'].iloc[-1]
                }
            
            # EMA trend following
            elif current_fast > current_slow and df['close'].iloc[-1] > current_fast:
                # Trend yukarı, fiyat EMA üstünde
                return {
                    'signal': 'BUY',
                    'confidence': 2,
                    'type': 'EMA_TREND',
                    'price': df['close'].iloc[-1]
                }
            
            elif current_fast < current_slow and df['close'].iloc[-1] < current_fast:
                # Trend aşağı, fiyat EMA altında
                return {
                    'signal': 'SELL',
                    'confidence': 2,
                    'type': 'EMA_TREND',
                    'price': df['close'].iloc[-1]
                }
                
        except Exception as e:
            self.logger.warning(f"EMA sinyal hatası: {e}")
        
        return None
    
    def get_rsi_signal(self, df):
        """RSI aşırı alım/satım sinyali"""
        try:
            current_rsi = df['rsi'].iloc[-1]
            prev_rsi = df['rsi'].iloc[-2]
            
            if pd.isna(current_rsi):
                return None
            
            # RSI oversold'dan çıkış
            if prev_rsi <= self.rsi_oversold and current_rsi > self.rsi_oversold:
                return {
                    'signal': 'BUY',
                    'confidence': 2,
                    'type': 'RSI_OVERSOLD',
                    'price': df['close'].iloc[-1]
                }
            
            # RSI overbought'tan çıkış
            elif prev_rsi >= self.rsi_overbought and current_rsi < self.rsi_overbought:
                return {
                    'signal': 'SELL',
                    'confidence': 2,
                    'type': 'RSI_OVERBOUGHT',
                    'price': df['close'].iloc[-1]
                }
                
        except Exception as e:
            self.logger.warning(f"RSI sinyal hatası: {e}")
        
        return None
    
    def get_macd_signal(self, df):
        """MACD sinyal çizgisi geçişi"""
        try:
            current_macd = df['macd'].iloc[-1]
            current_signal = df['macd_signal'].iloc[-1]
            prev_macd = df['macd'].iloc[-2]
            prev_signal = df['macd_signal'].iloc[-2]
            
            if pd.isna(current_macd) or pd.isna(current_signal):
                return None
            
            # MACD yukarı kesişim
            if prev_macd <= prev_signal and current_macd > current_signal:
                return {
                    'signal': 'BUY',
                    'confidence': 2,
                    'type': 'MACD_BULLISH',
                    'price': df['close'].iloc[-1]
                }
            
            # MACD aşağı kesişim
            elif prev_macd >= prev_signal and current_macd < current_signal:
                return {
                    'signal': 'SELL',
                    'confidence': 2,
                    'type': 'MACD_BEARISH',
                    'price': df['close'].iloc[-1]
                }
                
        except Exception as e:
            self.logger.warning(f"MACD sinyal hatası: {e}")
        
        return None
    
    def get_price_action_signal(self, df):
        """Basit price action sinyali"""
        try:
            # Son 3 mumun analizi
            if len(df) < 3:
                return None
            
            recent_closes = df['close'].tail(3).values
            recent_highs = df['high'].tail(3).values
            recent_lows = df['low'].tail(3).values
            
            current_close = recent_closes[-1]
            prev_close = recent_closes[-2]
            
            # Güçlü yukarı hareket
            if current_close > prev_close and (current_close - prev_close) > self.min_price_move:
                return {
                    'signal': 'BUY',
                    'confidence': 1,
                    'type': 'PRICE_MOMENTUM',
                    'price': current_close
                }
            
            # Güçlü aşağı hareket
            elif current_close < prev_close and (prev_close - current_close) > self.min_price_move:
                return {
                    'signal': 'SELL',
                    'confidence': 1,
                    'type': 'PRICE_MOMENTUM',
                    'price': current_close
                }
                
        except Exception as e:
            self.logger.warning(f"Price action sinyal hatası: {e}")
        
        return None
    
    def count_positions(self):
        """Pozisyon sayısı"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return 0
        return len([p for p in positions if p.magic == self.magic_number])
    
    def place_order(self, signal_data):
        """Geliştirilmiş emir yerleştirme"""
        try:
            if self.count_positions() >= self.max_positions:
                self.logger.debug(f"Max pozisyon sınırı: {self.max_positions}")
                return False
            
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return False
            
            signal_type = signal_data['signal']
            confidence = signal_data['confidence']
            signal_name = signal_data['type']
            
            # Symbol bilgisi
            symbol_info = mt5.symbol_info(self.symbol)
            if not symbol_info:
                return False
            
            # Pip değeri hesaplama
            if symbol_info.digits >= 3:
                pip_value = 0.1
            else:
                pip_value = 0.0001
            
            # Dinamik lot size (güven seviyesine göre)
            base_lot = self.lot_size
            if confidence >= 3:
                adjusted_lot = base_lot * 1.2  # %20 artır
            elif confidence >= 2:
                adjusted_lot = base_lot
            else:
                adjusted_lot = base_lot * 0.8  # %20 azalt
            
            # Minimum lot kontrolü
            adjusted_lot = max(adjusted_lot, symbol_info.volume_min)
            adjusted_lot = round(adjusted_lot, 2)
            
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
                "comment": f"{signal_name}_{confidence}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.successful_trades += 1
                self.logger.info(f"🚀 {signal_type} EMİR AÇILDI!")
                self.logger.info(f"   📊 Sinyal: {signal_name} (Güven: {confidence})")
                self.logger.info(f"   💰 Lot: {adjusted_lot}, Price: {price:.5f}")
                self.logger.info(f"   🎯 SL: {sl:.5f}, TP: {tp:.5f}")
                return True
            else:
                self.logger.warning(f"❌ Emir başarısız: {result.retcode} - {result.comment}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Emir hatası: {e}")
            return False
    
    def manage_positions(self):
        """Geliştirilmiş pozisyon yönetimi"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if not positions:
                return
            
            for pos in positions:
                if pos.magic != self.magic_number:
                    continue
                
                # Hızlı kar alma
                current_profit = pos.profit
                if current_profit > 5:  # 5 USD kar
                    self.close_position(pos.ticket, "Hızlı kar")
                    self.winning_streak += 1
                    self.losing_streak = 0
                
        except Exception as e:
            self.logger.error(f"Pozisyon yönetimi hatası: {e}")
    
    def close_position(self, ticket, reason=""):
        """Pozisyon kapatma"""
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
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"💰 Pozisyon kapatıldı: {reason}")
                return True
            
        except Exception as e:
            self.logger.error(f"Pozisyon kapatma hatası: {e}")
        
        return False
    
    def run_improved_scalping(self):
        """Geliştirilmiş scalping döngüsü"""
        self.logger.info("🚀 GELİŞTİRİLMİŞ SCALPING BOT BAŞLATILDI!")
        self.logger.info(f"📊 Symbol: {self.symbol}")
        self.logger.info(f"🎯 TP/SL: {self.take_profit_pips}/{self.stop_loss_pips} pip")
        self.logger.info(f"📈 EMA: {self.ema_fast}/{self.ema_slow}")
        self.logger.info(f"🔧 RSI: {self.use_rsi}, MACD: {self.use_macd}")
        
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                
                # Market koşulları
                if not self.check_market_conditions():
                    time.sleep(5)
                    continue
                
                # Pozisyon yönetimi
                self.manage_positions()
                
                # Veri al
                df = self.get_data()
                if df is None:
                    time.sleep(3)
                    continue
                
                # Çoklu sinyal kontrolü
                signal = self.generate_multiple_signals(df)
                if signal is None:
                    time.sleep(2)
                    continue
                
                # Emir ver
                if self.place_order(signal):
                    self.logger.info(f"✅ {signal['type']} sinyali ile işlem açıldı!")
                    time.sleep(5)
                
                # İstatistik
                if loop_count % 20 == 0:
                    success_rate = (self.successful_trades / max(self.total_signals, 1)) * 100
                    self.logger.info(f"📊 Başarı oranı: {success_rate:.1f}% ({self.successful_trades}/{self.total_signals})")
                
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("🛑 Bot durduruldu.")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    bot = ImprovedScalpingBot(
        symbol="XAUUSD",
        timeframe=mt5.TIMEFRAME_M1
    )
    
    print("🚀 GELİŞTİRİLMİŞ SCALPING BOT")
    print("✅ Çoklu sinyal sistemi (EMA + RSI + MACD + Price Action)")
    print("✅ Esnek filtreler (düşük eşikler)")
    print("✅ Dinamik lot sizing")
    print("✅ Hızlı pozisyon yönetimi")
    print("\n💡 Bu bot daha fazla işlem açacak şekilde optimize edildi!")
    print("🚀 Başlatılıyor... (Ctrl+C ile durdur)")
    
    bot.run_improved_scalping()