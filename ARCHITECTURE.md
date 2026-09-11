# Reflex — Architecture Design Document

## System Overview
Reflex is a delivery management system that connects Retailers, Dispatchers, and Riders through an async event-driven architecture. It provides real-time status visibility and proof of delivery for small Kenyan retailers.

## Tech Stack

|| Technology |  |

 Backend ---  Component 
 Python + Flask --- Technology
 Rapid prototyping, native support for async and SSE ---Why



 Real-time Updates --- Component
 server-Sent Events (SSE) --- Technology
 Simpler than WebSockets; fits our server-client flow ---Why



 Message Queue --- Component
 In-memory list (simulated) --- Technology
 Simulates RabbitMQ/SQS for the prototype --- Why




 Data Storage --- Component
 In-memory dict --- Technology
 Simulates a database; swap-ready for SQLite/Postgres --- Why




 Frontend --- Component
 Vanilla HTML/CSS/JS --- Technology
 Single-file deployment, no build step --- Why

## User Personas

 **Retailer** ---  Persona
 Logs a delivery request, Fill form (customer, phone,  address, item) --- Role 
 submit --- Primary Actions


 **Dispatcher** ---  Persona
 Assigns deliveries to riders --- Role 
 View open requests assign to available rider --- Primary Actions


 **Rider** ---  Persona
 Delivers and updates status --- Role 
 View assigned deliveries - mark Picked Up Delivered --- Primary Actions

## Data Model
Delivery {
id: string (e.g., "DEL-A1B2C3")
customer_name: string
customer_phone: string
delivery_address: string
item_description: string
status: "Requested" | "Assigned" | "Picked Up" | "Delivered"
assigned_rider: string | null
assigned_rider_name: string | null
created_at: timestamp
assigned_at: timestamp | null
picked_up_at: timestamp | null
delivered_at: timestamp | null
proof_of_delivery: string | null
}

Rider {
id: string (e.g., "RDR-001")
name: string
phone: string
active_deliveries: integer
}
## Status Flow
1. Retailer logs a delivery - status: "Requested"
2. Dispatcher assigns - job published to queue - worker processes - webhook confirms - status: "Assigned"
3. Rider marks picked up - job published - webhook confirms - status: "Picked Up"
4. Rider marks delivered - job published - webhook confirms - status: "Delivered" + proof captured

## API Endpoints


 '/' ---  Endpoint
 GET --- Method
 Serve the three-tab UI (Retailer, Dispatcher, Rider) --- Purpose    


 '/api/deliverie' ---  Endpoint
 GET --- Method
 List all deliveries --- Purpose 


 '/api/deliveries' ---  Endpoint
 POST --- Method
 Retailer logs a new delivery request --- Purpose 


 '/api/riders' ---  Endpoint
 GET --- Method
 List all riders --- Purpose 


 '/api/assign' ---  Endpoint
 POST --- Method
 Dispatcher assigns a delivery to a rider --- Purpose 


 '/api/rider/update' ---  Endpoint
 POST --- Method
 Rider updates delivery status --- Purpose 


 '/api/scan/<delivery_id>' ---  Endpoint
 GET --- Method
 Look up a delivery + verify proof of delivery --- Purpose 


 '/api/queue` ---  Endpoint
 GET --- Method
 Queue monitoring --- Purpose 


 '/api/stats' ---  Endpoint
 GET --- Method
 Dashboard statistics --- Purpose 


 '/api/stream' ---  Endpoint
 GET --- Method
 SSE real-time updates --- Purpose 


 '/webhook/rider-confirm' ---  Endpoint
 POST --- Method
 Simulated webhook callback from rider app --- Purpose 

