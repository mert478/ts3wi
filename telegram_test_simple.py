# Basit Telegram Test - requests olmadan
import urllib.request
import urllib.parse
import json
import logging

def test_telegram_simple():
    """Basit Telegram testi"""
    BOT_TOKEN = "7594813856:AAGYoqUnHkT6Mybo7L3goS-Rw_7dJ8bnRpU"
    CHAT_ID = "6694433256"
    
    message = "🤖 MegaTrend Bot Telegram Testi - Başarılı!"
    
    try:
        # URL hazırla
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        
        # Veri hazırla
        data = {
            'chat_id': CHAT_ID,
            'text': message,
            'parse_mode': 'HTML'
        }
        
        # POST isteği gönder
        data_encoded = urllib.parse.urlencode(data).encode('utf-8')
        req = urllib.request.Request(url, data=data_encoded, method='POST')
        req.add_header('Content-Type', 'application/x-www-form-urlencoded')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.loads(response.read().decode('utf-8'))
            
            if result.get('ok'):
                print("✅ Telegram testi başarılı!")
                print(f"Mesaj ID: {result['result']['message_id']}")
                return True
            else:
                print(f"❌ Telegram hatası: {result}")
                return False
                
    except Exception as e:
        print(f"❌ Bağlantı hatası: {e}")
        return False

if __name__ == "__main__":
    print("Telegram bağlantısı test ediliyor...")
    test_telegram_simple()