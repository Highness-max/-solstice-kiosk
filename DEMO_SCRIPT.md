&#x20;**Reflex — Demo Script**



&#x20;Intro (0:00-0:30)

"Hi, I'm SIR NCHOE LESHAN -(Highness-max). Today I'm presenting Reflex — an event-driven delivery management system for small Kenyan retailers."



&#x20;Problem (0:30-1:30)

"Small retailers currently manage deliveries over WhatsApp and phone calls. There's no record, no status visibility, no proof of delivery."



&#x20;Solution (1:30-2:30)

"Reflex solves this. Retailer logs a delivery, Dispatcher assigns it, Rider updates status. Everyone knows where every delivery stands."



&#x20;Architecture (2:30-4:00)

"We built this with Flask + SSE + a message queue. The flow is: Scan - Queue - Webhook - Complete."



&#x20;Demo (4:00-6:00)

\[Show the app running]

\- Scan ATT-001 - Shows "Pending"

\- Wait 5 seconds - Webhook arrives - Shows "Checked In"

\- Scan ATT-001 again - Shows "Already scanned"



&#x20;Trade-offs (6:00-7:00)

"We accepted three key trade-offs: in-memory storage, SSE over WebSockets, and a simple queue."



&#x20;Edge Cases (7:00-8:00)

"We handle duplicate scans, out-of-order webhooks, and API failures gracefully."



&#x20;Roadmap (8:00-9:00)

"Next: Persistent storage, retry logic, QR scanner integration."



&#x20;Q\&A (9:00-10:00)

"Happy to answer any questions."





