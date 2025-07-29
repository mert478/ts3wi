#!/usr/bin/env python3
"""
Gerekli bağımlılıkları kontrol eden script
"""

import sys

def check_dependencies():
    missing_packages = []
    
    # Gerekli paketleri kontrol et
    required_packages = {
        'MetaTrader5': 'MetaTrader5',
        'pandas': 'pandas',
        'numpy': 'numpy', 
        'talib': 'TA-Lib',
        'requests': 'requests'
    }
    
    print("🔍 Gerekli paketler kontrol ediliyor...")
    print("=" * 50)
    
    for package, display_name in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {display_name}: KURULU")
        except ImportError:
            print(f"❌ {display_name}: EKSİK")
            missing_packages.append(package)
    
    print("=" * 50)
    
    if missing_packages:
        print(f"❌ {len(missing_packages)} paket eksik!")
        print("\nEksik paketleri kurmak için:")
        for package in missing_packages:
            if package == 'talib':
                print(f"pip install TA-Lib")
            else:
                print(f"pip install {package}")
        print("\nTüm paketleri tek seferde kurmak için:")
        print("pip install MetaTrader5 pandas numpy requests TA-Lib")
        return False
    else:
        print("✅ Tüm gerekli paketler kurulu!")
        return True

if __name__ == "__main__":
    success = check_dependencies()
    sys.exit(0 if success else 1)