import urllib.request
import json
import psycopg2
from datetime import datetime

# ลิงก์ Session Pooler ที่เสถียร
DB_URI = "postgresql://postgres.fnccaedxxyzmfcicvdpg:Sinsawoo%402539@aws-0-ap-southeast-2.pooler.supabase.com:5432/postgres"

def fetch_real_data_absolute():
    conn = None
    cursor = None
    try:
        print("กำลังเชื่อมต่อฐานข้อมูล Supabase...")
        conn = psycopg2.connect(DB_URI, connect_timeout=15)
        conn.autocommit = True 
        cursor = conn.cursor()
        
        # 🌟 เพิ่มคอลัมน์ cctv_url ในฐานข้อมูล (ถ้ายังไม่มี) 🌟
        try:
            cursor.execute("ALTER TABLE flood_tracking ADD COLUMN IF NOT EXISTS cctv_url TEXT;")
            print("✅ ตรวจสอบ/เพิ่มคอลัมน์ CCTV ใน Database เรียบร้อย")
        except Exception as e:
            print(f"⚠️ ไม่สามารถเพิ่มคอลัมน์ได้: {e}")

        url = "https://api-v3.thaiwater.net/api/v1/thaiwater30/public/waterlevel"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        stations_data = []
        if isinstance(data, dict) and 'data' in data and 'waterlevel_data' in data['data']:
            stations_data = data['data']['waterlevel_data']
        elif isinstance(data, dict) and 'data' in data and isinstance(data['data'], list):
            stations_data = data['data']

        total_stations = len(stations_data)
        print(f"เตรียมบันทึกข้อมูลดิบทั้งหมด {total_stations} สถานี...")

        # 🌟 อัปเดต SQL ให้บันทึก cctv_url แยกลงไปต่างหากเลย 🌟
        sql_with_geom = """
            INSERT INTO flood_tracking (station_id, station_name, water_level, update_time, geom, cctv_url)
            VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s)
            ON CONFLICT (station_id) DO UPDATE SET 
                water_level = EXCLUDED.water_level, 
                station_name = EXCLUDED.station_name, 
                update_time = EXCLUDED.update_time,
                geom = EXCLUDED.geom,
                cctv_url = EXCLUDED.cctv_url;
        """
        
        sql_no_geom = """
            INSERT INTO flood_tracking (station_id, station_name, water_level, update_time, geom, cctv_url)
            VALUES (%s, %s, %s, %s, NULL, %s)
            ON CONFLICT (station_id) DO UPDATE SET 
                water_level = EXCLUDED.water_level, 
                station_name = EXCLUDED.station_name, 
                update_time = EXCLUDED.update_time,
                geom = NULL,
                cctv_url = EXCLUDED.cctv_url;
        """

        records_updated = 0
        
        for index, item in enumerate(stations_data):
            station = item.get('station', {})
            
            st_id = station.get('tele_station_oldcode') or station.get('id') or f"STN-UNKNOWN-{index}"
            st_name = station.get('tele_station_name', {}).get('th', 'ไม่ระบุชื่อ')
            
            geocode = item.get('geocode') or station.get('geocode') or {}
            prov = geocode.get('province_name', {}).get('th', 'ไม่ระบุจังหวัด') if isinstance(geocode.get('province_name'), dict) else 'ไม่ระบุจังหวัด'
            amp = geocode.get('amphoe_name', {}).get('th', 'ไม่ระบุอำเภอ') if isinstance(geocode.get('amphoe_name'), dict) else 'ไม่ระบุอำเภอ'
            
            # ไม่ต้องยัด || แล้ว เอาแค่ชื่อ, อำเภอ, จังหวัดพอ
            smart_name = f"{st_name}||{amp}||{prov}"
            
            # 🌟 ดึงลิงก์ CCTV มาเก็บไว้ต่างหาก
            cctv_url = 'ไม่มีกล้อง'
            if item.get('cctv_url'): cctv_url = item.get('cctv_url')
            elif station.get('tele_station_cctv'): cctv_url = station.get('tele_station_cctv')
            elif station.get('cctv_url'): cctv_url = station.get('cctv_url')
            elif station.get('cctv') and isinstance(station.get('cctv'), list) and len(station.get('cctv')) > 0:
                cctv_info = station.get('cctv')[0]
                if isinstance(cctv_info, dict):
                    cctv_url = cctv_info.get('cctv_url', 'ไม่มีกล้อง')
            
            # 🌟 เลือกระดับน้ำ (เอาระดับน้ำปกติก่อน ถ้าไม่มีค่อยเอา MSL)
            wl = item.get('waterlevel_m')
            if wl is None or wl == '': 
                wl = item.get('waterlevel_msl')
            
            wl_float = None 
            if wl not in [None, 'null', 'None', '']:
                try: 
                    temp_wl = float(wl)
                    if -999.99 <= temp_wl <= 999.99: wl_float = temp_wl
                except: pass
            
            lat = station.get('tele_station_lat')
            lon = station.get('tele_station_long')
            
            lat_float = None; lon_float = None
            if lat not in [None, 'null', 'None', '']:
                try: lat_float = float(lat)
                except: pass
            if lon not in [None, 'null', 'None', '']:
                try: lon_float = float(lon)
                except: pass

            try:
                # 🌟 ส่ง cctv_url แยกไปเลย
                if lat_float is not None and lon_float is not None:
                    cursor.execute(sql_with_geom, (str(st_id), smart_name, wl_float, datetime.now(), lon_float, lat_float, cctv_url))
                else:
                    cursor.execute(sql_no_geom, (str(st_id), smart_name, wl_float, datetime.now(), cctv_url))
                
                records_updated += 1
                if records_updated % 100 == 0: print(f"✅ ดำเนินการไปแล้ว {records_updated}/{total_stations} สถานี...")
                    
            except Exception as db_err:
                print(f"❌ ไม่สามารถบันทึกสถานี {st_id} ได้ เนื่องจาก {db_err}")

        print(f"🎉 อัปเดตข้อมูลและ CCTV สำเร็จ! บันทึกข้อมูลได้ทั้งหมด {records_updated} สถานี")

    except Exception as e:
        print(f"\n❌ เกิดข้อผิดพลาดหลัก: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

if __name__ == "__main__":
    fetch_real_data_absolute()