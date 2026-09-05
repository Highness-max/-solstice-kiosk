 Reflex — Trade-off Log

 Trade-off 1: In-Memory Storage vs. Database
- What it is: We used in-memory Python dicts instead of a database.
- Why accepted: This is a prototype. We needed to ship fast and prove the architecture works.
- Cost: Data is lost on server restart. No persistence.
- Would do differently: With more time, I'd add SQLite and a backup/recovery mechanism.

 Trade-off 2: SSE vs. WebSockets
- What it is: We used SSE for real-time updates instead of WebSockets.
- Why accepted: SSE is simpler to implement and fits our use case (server→client only).
- Cost: Cannot push updates from client to server (not needed for our flow).
- Would do differently: If we needed bi-directional communication, I'd switch to WebSockets.

 Trade-off 3: In-Memory Queue vs. RabbitMQ/Kafka
- What it is: We used a Python list as a queue instead of a real message broker.
- Why accepted: To avoid external dependencies and keep the system simple to run.
- Cost: Queue is not persistent; if the server restarts, pending jobs are lost.
- Would do differently: With more time, I'd use Redis or RabbitMQ for production.

 Trade-off 4: Single-File Deployment vs. Microservices
- What it is: Everything is in one `app.py` file.
- Why accepted: This is a prototype; microservices would add unnecessary complexity.
- Cost: Harder to scale individual components.
- Would do differently: I'd split into separate services (UI, API, Queue Worker) for production.

 Trade-off 5: Manual Testing vs. Automated Tests
- What it is: We tested manually instead of writing unit/integration tests.
- Why accepted: To meet the deadline and prove the concept works.
- Cost: No automated regression testing; manual testing is slow.
- Would do differently: I'd add pytest tests for the API and webhook endpoints.

