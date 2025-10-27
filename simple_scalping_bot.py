import MetaTrader5 as mt5
import pandas as pd
import numpy as np
import time
import logging
from datetime import datetime
import talib

# Basit loglama
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class SimpleScalpingBot:
    def __init__(self, symbol="XAUUSD+", timeframe=mt5.TIMEFRAME_M1):
        self.symbol = symbol
        self.timeframe = timeframe
        self.magic_number = 12345
        
        # SCALPING AYARLARI - BASİT VE ETKİLİ
        self.lot_size = 0.01
        self.take_profit_pips = 5    # 5 pip kazanç hedefi
        self.stop_loss_pips = 10     # 10 pip stop loss (1:0.5 risk/reward)
        self.max_positions = 3       # Max 3 pozisyon
        self.ema_fast = 5           # Hızlı EMA
        self.ema_slow = 20          # Yavaş EMA
        
        self.logger = logging.getLogger(__name__)
        self.initialize_mt5()
    
    def initialize_mt5(self):
        """MT5 bağlantısı"""
        if not mt5.initialize():
            self.logger.error("MT5 başlatılamadı!")
            return False
        
        if not mt5.symbol_select(self.symbol, True):
            self.logger.error(f"Symbol seçilemedi: {self.symbol}")
            return False
        
        self.logger.info(f"✅ {self.symbol} hazır - Scalping başlıyor!")
        return True
    
    def get_data(self, bars=50):
        """Veri al"""
        rates = mt5.copy_rates_from_pos(self.symbol, self.timeframe, 0, bars)
        if rates is None:
            return None
        
        df = pd.DataFrame(rates)
        df['time'] = pd.to_datetime(df['time'], unit='s')
        return df
    
    def generate_simple_signal(self, df):
        """BASİT VE ETKİLİ SİNYAL - Sadece EMA Crossover"""
        if len(df) < self.ema_slow:
            return None
        
        # EMA hesapla
        ema_fast = talib.EMA(df['close'].values, timeperiod=self.ema_fast)
        ema_slow = talib.EMA(df['close'].values, timeperiod=self.ema_slow)
        
        # Son 2 değer
        if len(ema_fast) < 2 or len(ema_slow) < 2:
            return None
        
        current_fast = ema_fast[-1]
        current_slow = ema_slow[-1]
        prev_fast = ema_fast[-2]
        prev_slow = ema_slow[-2]
        current_price = df['close'].iloc[-1]
        
        # Crossover sinyalleri
        if prev_fast <= prev_slow and current_fast > current_slow:
            # Golden Cross - BUY
            return {
                'signal': 'BUY',
                'price': current_price,
                'ema_fast': current_fast,
                'ema_slow': current_slow
            }
        elif prev_fast >= prev_slow and current_fast < current_slow:
            # Death Cross - SELL
            return {
                'signal': 'SELL', 
                'price': current_price,
                'ema_fast': current_fast,
                'ema_slow': current_slow
            }
        
        return None
    
    def count_positions(self):
        """Açık pozisyon sayısı"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return 0
        return len([p for p in positions if p.magic == self.magic_number])
    
    def place_order(self, signal_type):
        """Emir ver - BASİT VE HIZLI"""
        try:
            # Pozisyon kontrolü
            if self.count_positions() >= self.max_positions:
                self.logger.info(f"Max pozisyon sayısına ulaşıldı: {self.max_positions}")
                return False
            
            # Fiyat bilgisi
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return False
            
            symbol_info = mt5.symbol_info(self.symbol)
            point = symbol_info.point
            
            if signal_type == 'BUY':
                price = tick.ask
                order_type = mt5.ORDER_TYPE_BUY
                sl = price - (self.stop_loss_pips * point * 10)  # 10 pip = 10 * point * 10
                tp = price + (self.take_profit_pips * point * 10)
            else:  # SELL
                price = tick.bid
                order_type = mt5.ORDER_TYPE_SELL
                sl = price + (self.stop_loss_pips * point * 10)
                tp = price - (self.take_profit_pips * point * 10)
            
            # Emir gönder
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": self.lot_size,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 20,
                "magic": self.magic_number,
                "comment": "SimpleScalping",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.logger.info(f"🚀 {signal_type} EMİR AÇILDI! "
                               f"Price: {price:.5f}, SL: {sl:.5f}, TP: {tp:.5f}")
                return True
            else:
                self.logger.error(f"Emir başarısız: {result.retcode}")
                return False
                
        except Exception as e:
            self.logger.error(f"Emir hatası: {e}")
            return False
    
    def check_quick_profits(self):
        """Hızlı kar alma - 3 pip kar varsa kapat"""
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if not positions:
                return
            
            for pos in positions:
                if pos.magic != self.magic_number:
                    continue
                
                # 3 pip kar varsa kapat
                symbol_info = mt5.symbol_info(self.symbol)
                point = symbol_info.point
                min_profit_pips = 3
                min_profit_value = min_profit_pips * point * 10 * pos.volume * 100000 / 100
                
                if pos.profit >= min_profit_value:
                    # Pozisyonu kapat
                    tick = mt5.symbol_info_tick(self.symbol)
                    if tick is None:
                        continue
                    
                    if pos.type == mt5.POSITION_TYPE_BUY:
                        price = tick.bid
                        order_type = mt5.ORDER_TYPE_SELL
                    else:
                        price = tick.ask
                        order_type = mt5.ORDER_TYPE_BUY
                    
                    close_request = {
                        "action": mt5.TRADE_ACTION_DEAL,
                        "symbol": self.symbol,
                        "volume": pos.volume,
                        "type": order_type,
                        "position": pos.ticket,
                        "price": price,
                        "deviation": 20,
                        "magic": self.magic_number,
                        "comment": "Quick profit take",
                        "type_time": mt5.ORDER_TIME_GTC,
                        "type_filling": mt5.ORDER_FILLING_IOC,
                    }
                    
                    result = mt5.order_send(close_request)
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        self.logger.info(f"💰 Hızlı kâr alındı! Profit: ${pos.profit:.2f}")
                        
        except Exception as e:
            self.logger.error(f"Kar alma hatası: {e}")
    
    def run_scalping(self):
        """Ana scalping döngüsü"""
        self.logger.info("🔥 Basit Scalping Bot başlatıldı!")
        self.logger.info(f"📊 Timeframe: {'M1' if self.timeframe == mt5.TIMEFRAME_M1 else 'M5'}")
        self.logger.info(f"🎯 Hedef: {self.take_profit_pips} pip TP, {self.stop_loss_pips} pip SL")
        
        try:
            while True:
                # Veri al
                df = self.get_data()
                if df is None:
                    time.sleep(5)
                    continue
                
                # Hızlı kar kontrolü
                self.check_quick_profits()
                
                # Sinyal üret
                signal = self.generate_simple_signal(df)
                if signal is None:
                    time.sleep(2)  # Daha sık kontrol
                    continue
                
                # Emir ver
                if self.place_order(signal['signal']):
                    self.logger.info(f"✅ {signal['signal']} sinyali işlendi!")
                
                time.sleep(2)  # 2 saniyede bir kontrol (hızlı scalping)
                
        except KeyboardInterrupt:
            self.logger.info("Bot durduruldu.")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    # BASİT SCALPING BOT
    bot = SimpleScalpingBot(
        symbol="XAUUSD+",
        timeframe=mt5.TIMEFRAME_M1  # veya mt5.TIMEFRAME_M5
    )
    
    # Ayarları göster
    print(f"🎯 Take Profit: {bot.take_profit_pips} pip")
    print(f"🛑 Stop Loss: {bot.stop_loss_pips} pip") 
    print(f"📈 EMA Fast: {bot.ema_fast}, Slow: {bot.ema_slow}")
    print(f"💼 Max Pozisyon: {bot.max_positions}")
    print(f"💰 Lot Size: {bot.lot_size}")
    
    bot.run_scalping()