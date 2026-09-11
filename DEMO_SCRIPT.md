# Reflex — Demo Script

## Intro (0:00-0:30)
"Hi, I'm Sir Nchoe Leshan. Today I'm presenting Reflex — an event-driven delivery management system for small Kenyan retailers."

## Problem (0:30-1:30)
"Small retailers currently manage deliveries over WhatsApp and phone calls. There's no record of who's assigned, no status visibility, and no proof of delivery. A retailer loses an order because they forgot which rider took it."

## Solution (1:30-2:30)
"Reflex solves this. A Retailer logs a delivery request with customer name, phone, address, and item. A Dispatcher assigns it to a Rider. The Rider updates status as they go. Everyone sees the same real-time picture."

## Architecture (2:30-3:30)
"I built Reflex with Flask, Server-Sent Events, and a message queue. The flow is: Log - Queue - Worker - Webhook - Real-time update. Each persona gets their own view, but they share the same live state."

## Live Demo (3:30-4:30)
[Showing the app running]
- Retailer tab: Log a delivery for "Alice Wanjiru, Samsung TV, Karen"
- Dispatcher tab: Assign it to John Mwangi - status changes to "Assigned" (within 5-8s)
- Rider tab: Select John Mwangi - Mark "Picked Up" - Mark "Delivered"
- Retailer tab: Scan the Delivery ID - see Proof of Delivery with timestamp + rider name

## Trade-offs (4:30-5:00)
"We accepted three key trade-offs: in-memory storage (fast to ship, loses data on restart), SSE over WebSockets (simpler, one-way), and an in-memory queue (no external deps). Every one has a clear path to production."

## Close (5:00)
"Thank you. Happy to take questions." It hasn't been easy especially for a complete beginner like me, but I appreciate the tasks given since they make us dig deeper and at least understand some concepts like APIs on our, which I believe will come in handy once we start the software engineering program.