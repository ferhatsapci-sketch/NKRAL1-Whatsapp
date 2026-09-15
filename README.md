# NKRAL1 – iPad + WhatsApp sürümü

Bu sürüm bilgisayarda sürekli çalıştırılmak yerine iPad üzerinden kurulup yönetilebilecek şekilde hazırlanmıştır. Uygulama **Render** üzerinde sürekli çalışan bir web servisi olarak yayınlanır. iPad yalnızca kurulumu/yönetimi ve TradingView/WhatsApp kullanımını yapar.

## Mimari
TradingView Watchlist Alerts → HTTPS Webhook → NKRAL1 → WhatsApp Cloud API → iPad

TradingView webhookları için HTTPS gerekir; 80/443 dışındaki portlar kabul edilmez ve alıcı 3 saniyeden uzun cevap verirse istek iptal edilebilir. Bu nedenle yerel iPad bağlantısı kullanılmaz.

## iPad'den kurulum
1. GitHub.com'a Safari ile gir ve yeni bir **Private** repository oluştur.
2. Bu klasördeki dosyaları repository'ye yükle: `app.py`, `requirements.txt`, `Dockerfile`, `render.yaml`, `NKRAL1_4H_Daily.pine`.
3. Render.com'a Safari ile gir, GitHub hesabını bağla ve bu repository'yi seç.
4. `render.yaml` üzerinden web service oluştur veya Docker runtime ile yeni Web Service oluştur.
5. Servisin Environment Variables bölümüne şu değerleri ekle:
   - `WHATSAPP_ENABLED=true`
   - `WHATSAPP_API_VERSION=<desteklenen Meta Graph API sürümü>`
   - `WHATSAPP_PHONE_NUMBER_ID=<Meta Phone Number ID>`
   - `WHATSAPP_ACCESS_TOKEN=<Meta access token>`
   - `WHATSAPP_TO=<alıcı WhatsApp numarası, ülke koduyla>`
   - `WHATSAPP_TEMPLATE_NAME=nkral1_signal_alert`
   - `WHATSAPP_TEMPLATE_LANGUAGE=tr`
   - `WEBHOOK_SECRET=<güçlü rastgele değer>`
   - `DB_PATH=/data/nkral1.db`
6. Deploy tamamlanınca Render sana `https://...onrender.com` benzeri HTTPS adresi verir.
7. Dashboard: `https://...onrender.com/`
8. Webhook: `https://...onrender.com/webhook?secret=WEBHOOK_SECRET`.

## WhatsApp template
Meta WhatsApp Manager'da şu template'i oluştur/onaylat:

NKRAL1 {{1}} SİNYALİ
Hisse: {{2}}
Periyot: {{3}}
Fiyat: {{4}}
Zaman: {{5}}

Template adı: `nkral1_signal_alert`
Dil: `tr`

## TradingView
`NKRAL1_4H_Daily.pine` scriptini TradingView'e ekle. Watchlist için 4 ayrı alert oluştur:
- 4H AL – UT Long
- 4H SAT – UT Short
- Daily AL – UT Long
- Daily SAT – UT Short

Webhook mesajı:
```json
{
  "strategy": "NKRAL1",
  "action": "AL",
  "symbol": "{{exchange}}:{{ticker}}",
  "price": "{{close}}",
  "timeframe": "{{interval}}",
  "time": "{{time}}"
}
```
SAT alertinde `action` değeri `SAT` yapılır.

## Güvenlik
Access Token'ı GitHub'a koyma. Render Environment Variables içine gir. `.env` dosyasını repository'ye yükleme. `WEBHOOK_SECRET` değerini de yalnızca Render ve TradingView'de kullan.

## Not
Render'ın sürekli çalışan web service planı kullanılır; webhook bildirim sisteminde uykuya geçen ücretsiz servislerden kaçınmak için bu sürümde kalıcı servis yaklaşımı tercih edilmiştir.
