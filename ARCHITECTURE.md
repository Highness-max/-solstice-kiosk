Reflex — Architecture Design Document

System Overview
Reflex is a delivery management system that connects Retailers, Dispatchers, and Riders through an event-driven architecture.

Tech Stack

 
 Backend  --  Component

 Python + Flask  -- Technology

 Rapid prototyping, sync/async support -- Why




 Real-time Updates --  Component

 Server-Sent Events (SSE)  -- Technology

 Lighter than WebSockets, built into Flask   -- Why




 Message Queue  --  Component

 In-memory list (simulated)  -- Technology

 Simulates RabbitMQ/Kafka for prototype   --  Why




 Data Storage --   Component

 In-memory dict   -- Technology

 Simulates database; designed to swap with SQLite/Postgres -- Why




 Frontend        --  Component

 Vanilla HTML/CSS/JS   -- Technology

 Single-file deployment, no build step -- Why


 Data Model

Attendee {
id: string (e.g., "ATT-001")
name: string
email: string
checked_in: boolean
pending: boolean
checked_in_at: timestamp
print_failed: boolean
}

Print Job {
ticket_id: string
attendee_id: string
attendee_name: string
timestamp: timestamp
}




Status Flow
1. Retailer (Attendee) scans QR - Publishes to queue
2. Dispatcher (Kiosk) shows "Pending"
3. Rider (Printer) processes job - Calls webhook
4. Status updates to "Checked In" (real-time via SSE)
5. Duplicate scan - Rejected with 409 Conflict


 API Endpoints
| Endpoint | Method | Purpose |


 '/'    -- Endpoint 

 GET    -- Method 

 Serve the kiosk UI  --  Purpose




 '/api/attendees'  -- Endpoint 


 GET             -- Method 


 List all attendees --  Purpose




 '/api/scan'    -- Endpoint 


 POST        -- Method 

 Submit print request --  Purpose




 '/webhook/print-complete'  -- Endpoint 


  POST      --- Method 


 Vendor callback --  Purpose





 '/api/stream'  -- Endpoint 


 GET        --- Method 

 SSE real-time updates  --  Purpose





 '/api/queue'   -- Endpoint 


 GET    --- Method 


 Queue monitoring   --  Purpose






                    SLIDE DECK OUTLINE                               

                                                                     
  SLIDE 1: Title                                                    

  "Reflex — Event-Driven Delivery Management"     
                  
                                                                     
  SLIDE 2: The Problem                                              
  "Small retailers manage deliveries via WhatsApp — no tracking."   

                                                                    
  SLIDE 3: The Solution                                             
  "One system: Retailer logs, Dispatcher assigns, Rider delivers." 

                                                                   
  SLIDE 4: The Architecture (High Level)                           
  "Queue + Webhooks + SSE = Event-Driven"   
                       
                                                                   
  SLIDE 5: The Data Model                                          
  "Attendee status: Pending → Checked In"  
                        
                                                                   
  SLIDE 6: The Status Flow                                         
  "Scan - Queue → Webhook - Complete"      
                        
                                                                   
  SLIDE 7: User Personas                                           
  "Retailer, Dispatcher, Rider — each has a role"  
                
                                                                   
  SLIDE 8: Trade-offs                                              
  "We chose resilience over speed, future-proofing over simplicity"                                                                   
  SLIDE 9: Edge Cases                                               
  "Duplicate scans, out-of-order webhooks, API failures" 
          
                                                                   
  SLIDE 10: Roadmap                                                
  "Next: Persistent storage, retry logic, QR scanner"              
                                                                   






