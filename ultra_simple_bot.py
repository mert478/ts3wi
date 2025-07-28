import MetaTrader5 as mt5
import time
import logging

# Basit loglama
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class UltraSimpleBot:
    def __init__(self, symbol="XAUUSD"):
        self.symbol = symbol
        self.magic_number = 99999
        self.lot_size = 0.01
        self.take_profit_pips = 2    # Sadece 2 pip hedef
        self.stop_loss_pips = 5      # 5 pip stop
        
        self.logger = logging.getLogger(__name__)
        self.last_price = None
        self.position_count = 0
        
        self.initialize_mt5()
    
    def initialize_mt5(self):
        """MT5 başlat"""
        if not mt5.initialize():
            print("❌ MT5 başlatılamadı!")
            return False
        
        # Symbol variants dene
        variants = [self.symbol, self.symbol + "+", "XAUUSD.", "GOLD"]
        for variant in variants:
            if mt5.symbol_select(variant, True):
                self.symbol = variant
                print(f"✅ Symbol bulundu: {self.symbol}")
                break
        else:
            print("❌ Hiçbir symbol bulunamadı!")
            return False
        
        return True
    
    def get_current_price(self):
        """Mevcut fiyatı al"""
        tick = mt5.symbol_info_tick(self.symbol)
        if tick is None:
            return None
        return (tick.bid + tick.ask) / 2  # Orta fiyat
    
    def count_my_positions(self):
        """Kendi pozisyonlarını say"""
        positions = mt5.positions_get(symbol=self.symbol)
        if not positions:
            return 0
        return len([p for p in positions if p.magic == self.magic_number])
    
    def place_simple_order(self, order_type):
        """Basit emir ver"""
        try:
            tick = mt5.symbol_info_tick(self.symbol)
            if tick is None:
                return False
            
            if order_type == "BUY":
                price = tick.ask
                sl = price - (self.stop_loss_pips * 0.1)
                tp = price + (self.take_profit_pips * 0.1)
                mt5_type = mt5.ORDER_TYPE_BUY
            else:  # SELL
                price = tick.bid
                sl = price + (self.stop_loss_pips * 0.1)
                tp = price - (self.take_profit_pips * 0.1)
                mt5_type = mt5.ORDER_TYPE_SELL
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": self.lot_size,
                "type": mt5_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "deviation": 100,
                "magic": self.magic_number,
                "comment": "UltraSimple",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": mt5.ORDER_FILLING_IOC,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                print(f"🚀 {order_type} EMİR AÇILDI! Price: {price:.2f}")
                return True
            else:
                print(f"❌ Emir başarısız: {result.retcode}")
                return False
                
        except Exception as e:
            print(f"❌ Hata: {e}")
            return False
    
    def run_ultra_simple(self):
        """Ultra basit trading - sadece fiyat hareketine göre"""
        print("🔥 ULTRA SİMPLE BOT BAŞLATILDI!")
        print(f"📊 Symbol: {self.symbol}")
        print(f"🎯 Hedef: {self.take_profit_pips} pip TP, {self.stop_loss_pips} pip SL")
        print("🎲 Strateji: Rastgele fiyat hareketi takibi")
        
        trade_counter = 0
        
        try:
            while True:
                # Mevcut fiyat
                current_price = self.get_current_price()
                if current_price is None:
                    time.sleep(1)
                    continue
                
                # İlk fiyat kaydı
                if self.last_price is None:
                    self.last_price = current_price
                    print(f"📊 İlk fiyat: {current_price:.2f}")
                    time.sleep(1)
                    continue
                
                # Pozisyon kontrolü
                current_positions = self.count_my_positions()
                
                # Maksimum 2 pozisyon
                if current_positions >= 2:
                    time.sleep(2)
                    continue
                
                # Fiyat değişimi
                price_change = current_price - self.last_price
                
                # 0.1 pip'ten fazla hareket varsa işlem aç
                if abs(price_change) >= 0.05:  # 0.05 = 0.5 pip (çok düşük)
                    trade_counter += 1
                    
                    if price_change > 0:
                        # Fiyat yükseldi - BUY
                        print(f"🟢 #{trade_counter} - Fiyat YÜKSELDİ: {price_change:.3f} - BUY açılıyor...")
                        if self.place_simple_order("BUY"):
                            print(f"✅ BUY işlemi açıldı!")
                    else:
                        # Fiyat düştü - SELL
                        print(f"🔴 #{trade_counter} - Fiyat DÜŞTÜ: {price_change:.3f} - SELL açılıyor...")
                        if self.place_simple_order("SELL"):
                            print(f"✅ SELL işlemi açıldı!")
                    
                    # Fiyatı güncelle
                    self.last_price = current_price
                    time.sleep(3)  # İşlem sonrası bekle
                else:
                    print(f"⏳ Fiyat: {current_price:.2f} (değişim: {price_change:.3f}) - Bekleniyor...")
                    time.sleep(1)
                
        except KeyboardInterrupt:
            print("🛑 Bot durduruldu.")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    bot = UltraSimpleBot(symbol="XAUUSD")
    bot.run_ultra_simple()