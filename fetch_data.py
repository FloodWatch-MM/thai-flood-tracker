import requests
import psycopg2
from datetime import datetime

# ⚠️ สำคัญ: นำ Connection String (URI) ที่คุณใส่รหัสผ่านแล้ว มาวางแทนที่ข้อความด้านล่างนี้
DB_URI = "postgresql://postgres.fnccaedxxyzmfcicvdpg:Sinsawoo%402539@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

def fetch_and_save_data():
    try:
        # 1. เชื่อมต่อฐานข้อมูล Supabase
        print("กำลังเชื่อมต่อฐานข้อมูล Supabase...")
        conn = psycopg2.connect(DB_URI)
        cursor = conn.cursor()
        print("เชื่อมต่อสำเร็จ!")

        # 2. จำลองข้อมูลระดับน้ำ (เพื่อให้ทดสอบระบบได้ทันที ระหว่างรอขอ API Key ของจริงจาก สสน.)
        # ข้อมูลสมมติของ 3 สถานีหลัก
        mock_api_data = [
            {"id": "STN01", "name": "สถานีสะพานพระราม 8", "water_level": 1.50, "lat": 13.7699, "lon": 100.4950},
            {"id": "STN02", "name": "สถานีบางนา", "water_level": 0.85, "lat": 13.6738, "lon": 100.6068},
            {"id": "STN03", "name": "สถานีรังสิต (เสี่ยงน้ำท่วม)", "water_level": 2.80, "lat": 13.9858, "lon": 100.6060}
        ]

        print("กำลังบันทึกข้อมูลลงฐานข้อมูล...")
        for station in mock_api_data:
            update_time = datetime.now()

            # SQL สำหรับเพิ่มข้อมูลใหม่ หรืออัปเดตข้อมูลเดิมถ้ามี station_id ซ้ำกัน (Upsert)
            sql = """
                INSERT INTO flood_tracking (station_id, station_name, water_level, update_time, geom)
                VALUES (%s, %s, %s, %s, ST_SetSRID(ST_MakePoint(%s, %s), 4326))
                ON CONFLICT (station_id) 
                DO UPDATE SET water_level = EXCLUDED.water_level, update_time = EXCLUDED.update_time;
            """
            
            # รันคำสั่ง SQL (PostGIS ใช้ลำดับพิกัดเป็น Longitude, Latitude)
            cursor.execute(sql, (
                station['id'], 
                station['name'], 
                station['water_level'], 
                update_time, 
                station['lon'], 
                station['lat']
            ))

        # 3. ยืนยันการบันทึกข้อมูล
        conn.commit()
        print("✅ บันทึกข้อมูลสำเร็จ! คุณสามารถกลับไปเช็คข้อมูลในหน้า Table ของ Supabase ได้เลย")

    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาด: {e}")
    finally:
        # ปิดการเชื่อมต่อเสมอเพื่อไม่ให้เปลืองทรัพยากรเซิร์ฟเวอร์
        if 'cursor' in locals(): cursor.close()
        if 'conn' in locals(): conn.close()

if __name__ == "__main__":
    fetch_and_save_data()