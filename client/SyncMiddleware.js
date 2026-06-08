// client/SyncMiddleware.js
class SyncMiddleware {
  constructor(apiBaseUrl, authToken) {
    this.apiBaseUrl = apiBaseUrl;
    this.authToken  = authToken;
    this.dbName     = "sync_queue";
    this.db         = null;

    this._initDB();
    window.addEventListener("online",  () => this.flush());
    window.addEventListener("offline", () => console.log("[Sync] Gone offline — queueing ops"));
  }

  async _initDB() {
    return new Promise((resolve, reject) => {
      const req = indexedDB.open(this.dbName, 1);
      req.onupgradeneeded = (e) => {
        const db    = e.target.result;
        const store = db.createObjectStore("operations", { keyPath: "id" });
        store.createIndex("status",    "status",    { unique: false });
        store.createIndex("timestamp", "timestamp", { unique: false });
      };
      req.onsuccess = (e) => { this.db = e.target.result; resolve(); };
      req.onerror   = reject;
    });
  }

  /**
   * The main entry point. Call this instead of hitting your API directly.
   * It decides whether to send now or queue for later.
   */
  async write(operation) {
    const op = {
      id:              crypto.randomUUID(),
      idempotency_key: crypto.randomUUID(),
      timestamp:       new Date().toISOString(),
      status:          "pending",
      ...operation,
    };

    if (navigator.onLine) {
      try {
        await this._sendToServer([op]);
        op.status = "synced";
      } catch (err) {
        console.warn("[Sync] Online but send failed, queuing:", err);
        op.status = "pending";
        await this._storeLocally(op);
      }
    } else {
      await this._storeLocally(op);
    }

    return op.id;
  }

  async flush() {
    console.log("[Sync] Back online — flushing queue...");
    const pending = await this._getPending();
    if (!pending.length) return;

    try {
      await this._sendToServer(pending);
      await this._markAllSynced(pending.map(op => op.id));
      console.log(`[Sync] Flushed ${pending.length} operations`);
    } catch (err) {
      console.error("[Sync] Flush failed:", err);
    }
  }

  async _sendToServer(ops) {
    const res = await fetch(`${this.apiBaseUrl}/sync/bulk/`, {
      method:  "POST",
      headers: {
        "Content-Type":  "application/json",
        "Authorization": `Bearer ${this.authToken}`,
        "X-Device-ID":   this._getDeviceId(),
      },
      body: JSON.stringify({ operations: ops }),
    });
    if (!res.ok) throw new Error(`Server error: ${res.status}`);
    return res.json();
  }

  async _storeLocally(op) {
    const tx    = this.db.transaction("operations", "readwrite");
    const store = tx.objectStore("operations");
    store.put(op);
  }

  async _getPending() {
    return new Promise((resolve) => {
      const tx      = this.db.transaction("operations", "readonly");
      const store   = tx.objectStore("operations");
      const index   = store.index("status");
      const req     = index.getAll("pending");
      req.onsuccess = (e) => resolve(e.target.result);
    });
  }

  async _markAllSynced(ids) {
    const tx    = this.db.transaction("operations", "readwrite");
    const store = tx.objectStore("operations");
    ids.forEach(id => {
      const req = store.get(id);
      req.onsuccess = (e) => {
        const op = e.target.result;
        if (op) { op.status = "synced"; store.put(op); }
      };
    });
  }

  _getDeviceId() {
    let id = localStorage.getItem("device_id");
    if (!id) { id = crypto.randomUUID(); localStorage.setItem("device_id", id); }
    return id;
  }
}

// Usage — drop-in replacement for your existing API calls
const sync = new SyncMiddleware("https://your-api.com/api", userToken);

// Instead of: await fetch('/api/orders/', { method: 'POST', body: ... })
// You do:
await sync.write({
  operation_type:  "CREATE",
  collection:      "orders",
  document_id:     crypto.randomUUID(),
  payload:         { status: "pending", amount: 5000 },
  client_timestamp: new Date().toISOString(),
});
