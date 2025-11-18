# FIX Protocol Adapter Integration

## Overview
Financial Information eXchange (FIX) protocol adapter for connecting to brokers and exchanges.

## FIX Protocol Versions
- FIX 4.2 (legacy)
- FIX 4.4 (most common)
- FIX 5.0 SP2 (latest)

## Architecture

```
[Trading Engine] → [FIX Adapter] → [FIX Session Manager] → [Broker FIX Gateway]
                                              ↓
                                    [Message Queue]
                                              ↓
                                    [Order State Machine]
```

## Components

### 1. FIX Session Manager
Manages FIX sessions with multiple brokers.

```typescript
// supabase/functions/fix-session-manager/index.ts
interface FIXConfig {
  senderCompID: string;
  targetCompID: string;
  host: string;
  port: number;
  version: "FIX.4.4";
  heartbeatInterval: number; // seconds
}

interface FIXSession {
  id: string;
  broker: string;
  status: "connecting" | "connected" | "disconnected";
  lastHeartbeat: Date;
  sequenceNumber: number;
}

class FIXSessionManager {
  private sessions: Map<string, FIXSession> = new Map();
  private socket: Deno.TcpConn | null = null;

  async connect(config: FIXConfig): Promise<void> {
    console.log(`Connecting to ${config.host}:${config.port}`);
    
    this.socket = await Deno.connect({
      hostname: config.host,
      port: config.port,
    });

    // Send logon message
    const logonMsg = this.buildLogonMessage(config);
    await this.send(logonMsg);

    // Start heartbeat
    this.startHeartbeat(config.heartbeatInterval);
  }

  private buildLogonMessage(config: FIXConfig): string {
    const msgSeqNum = 1;
    const sendingTime = this.getUTCTimestamp();
    
    const fields = [
      "8=" + config.version,           // BeginString
      "35=A",                          // MsgType (Logon)
      "34=" + msgSeqNum,               // MsgSeqNum
      "49=" + config.senderCompID,     // SenderCompID
      "52=" + sendingTime,             // SendingTime
      "56=" + config.targetCompID,     // TargetCompID
      "98=0",                          // EncryptMethod (None)
      "108=" + config.heartbeatInterval, // HeartBtInt
    ];

    const body = fields.slice(2).join("\x01");
    const length = body.length;
    
    const headerFields = [
      "8=" + config.version,
      "9=" + length,
      ...fields.slice(2),
    ];

    const msgWithoutChecksum = headerFields.join("\x01") + "\x01";
    const checksum = this.calculateChecksum(msgWithoutChecksum);
    
    return msgWithoutChecksum + "10=" + checksum + "\x01";
  }

  private calculateChecksum(msg: string): string {
    let sum = 0;
    for (let i = 0; i < msg.length; i++) {
      sum += msg.charCodeAt(i);
    }
    const checksum = (sum % 256).toString().padStart(3, "0");
    return checksum;
  }

  private getUTCTimestamp(): string {
    const now = new Date();
    return now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  }

  private async send(message: string): Promise<void> {
    if (!this.socket) throw new Error("Not connected");
    
    const encoder = new TextEncoder();
    await this.socket.write(encoder.encode(message));
    
    console.log("FIX OUT:", message.replace(/\x01/g, "|"));
  }

  private startHeartbeat(interval: number): void {
    setInterval(async () => {
      const heartbeatMsg = this.buildHeartbeatMessage();
      await this.send(heartbeatMsg);
    }, interval * 1000);
  }

  private buildHeartbeatMessage(): string {
    // Implementation similar to logon
    return ""; // Simplified
  }

  async disconnect(): Promise<void> {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
```

### 2. Order Entry
```typescript
interface NewOrderSingle {
  clOrdID: string;          // Client Order ID
  symbol: string;           // Ticker
  side: "1" | "2";          // 1=Buy, 2=Sell
  orderQty: number;         // Quantity
  ordType: "1" | "2";       // 1=Market, 2=Limit
  price?: number;           // Limit price (if limit order)
  timeInForce: "0" | "1";   // 0=Day, 1=GTC
  account?: string;         // Account number
}

function buildNewOrderSingle(order: NewOrderSingle, config: FIXConfig): string {
  const msgSeqNum = getNextSeqNum();
  const sendingTime = getUTCTimestamp();
  
  const fields = [
    "8=" + config.version,
    "35=D",                         // MsgType (NewOrderSingle)
    "34=" + msgSeqNum,
    "49=" + config.senderCompID,
    "52=" + sendingTime,
    "56=" + config.targetCompID,
    "11=" + order.clOrdID,          // ClOrdID
    "21=1",                         // HandlInst (Automated)
    "38=" + order.orderQty,         // OrderQty
    "40=" + order.ordType,          // OrdType
    "54=" + order.side,             // Side
    "55=" + order.symbol,           // Symbol
    "59=" + order.timeInForce,      // TimeInForce
  ];

  if (order.ordType === "2" && order.price) {
    fields.push("44=" + order.price); // Price
  }

  if (order.account) {
    fields.push("1=" + order.account); // Account
  }

  return assembleFIXMessage(fields);
}
```

### 3. Execution Report Handler
```typescript
interface ExecutionReport {
  orderID: string;
  execID: string;
  execType: string;
  ordStatus: string;
  symbol: string;
  side: string;
  leavesQty: number;
  cumQty: number;
  avgPx: number;
  text?: string;
}

function parseExecutionReport(fixMessage: string): ExecutionReport {
  const fields = fixMessage.split("\x01");
  const data: Record<string, string> = {};
  
  fields.forEach(field => {
    const [tag, value] = field.split("=");
    if (tag && value) data[tag] = value;
  });

  return {
    orderID: data["37"],      // OrderID
    execID: data["17"],       // ExecID
    execType: data["150"],    // ExecType
    ordStatus: data["39"],    // OrdStatus
    symbol: data["55"],       // Symbol
    side: data["54"],         // Side
    leavesQty: parseFloat(data["151"] || "0"), // LeavesQty
    cumQty: parseFloat(data["14"] || "0"),     // CumQty
    avgPx: parseFloat(data["6"] || "0"),       // AvgPx
    text: data["58"],         // Text
  };
}

async function handleExecutionReport(report: ExecutionReport): Promise<void> {
  // Update trade in database
  await supabase.from("trades").update({
    status: mapOrdStatusToInternal(report.ordStatus),
    filled_quantity: report.cumQty,
    avg_fill_price: report.avgPx,
    broker_order_id: report.orderID,
    updated_at: new Date().toISOString(),
  }).eq("client_order_id", report.orderID);

  // Log audit event
  await supabase.from("audit_logs").insert({
    user_id: (await getCurrentUser()).id,
    action: "execution_report_received",
    resource_type: "trade",
    resource_id: report.orderID,
    details: report,
  });

  // Notify user
  await notifyTrader(report);
}

function mapOrdStatusToInternal(ordStatus: string): string {
  const statusMap: Record<string, string> = {
    "0": "new",            // New
    "1": "partial",        // Partially filled
    "2": "filled",         // Filled
    "4": "cancelled",      // Canceled
    "8": "rejected",       // Rejected
  };
  return statusMap[ordStatus] || "unknown";
}
```

### 4. Order State Machine
```typescript
interface OrderState {
  id: string;
  status: "pending" | "sent" | "acknowledged" | "partial" | "filled" | "cancelled" | "rejected";
  events: OrderEvent[];
}

interface OrderEvent {
  timestamp: Date;
  type: string;
  data: any;
}

class OrderStateMachine {
  private state: OrderState;

  constructor(orderId: string) {
    this.state = {
      id: orderId,
      status: "pending",
      events: [],
    };
  }

  transition(event: OrderEvent): void {
    this.state.events.push(event);

    switch (event.type) {
      case "order_sent":
        this.state.status = "sent";
        break;
      case "order_acknowledged":
        this.state.status = "acknowledged";
        break;
      case "partial_fill":
        this.state.status = "partial";
        break;
      case "fill":
        this.state.status = "filled";
        break;
      case "cancel_acknowledged":
        this.state.status = "cancelled";
        break;
      case "reject":
        this.state.status = "rejected";
        break;
    }

    // Persist state
    this.persistState();
  }

  private async persistState(): Promise<void> {
    await supabase.from("order_states").upsert({
      order_id: this.state.id,
      status: this.state.status,
      events: this.state.events,
      updated_at: new Date().toISOString(),
    });
  }
}
```

## Broker Connectivity

### Supported Brokers (Zimbabwe Context)
- **Morgan & Co**: FIX 4.4, ZSE access
- **IH Securities**: FIX 4.4, ZSE + international
- **SECZ**: FIX 4.2, ZSE

### Connection Configuration
```typescript
const brokerConfigs: Record<string, FIXConfig> = {
  morgan: {
    senderCompID: "ZIMAITRADER",
    targetCompID: "MORGAN",
    host: "fix.morgan.co.zw",
    port: 5001,
    version: "FIX.4.4",
    heartbeatInterval: 30,
  },
  ih_securities: {
    senderCompID: "ZIMAITRADER",
    targetCompID: "IHSEC",
    host: "fix.ih.co.zw",
    port: 5001,
    version: "FIX.4.4",
    heartbeatInterval: 30,
  },
};
```

## Error Handling & Recovery

### Session Recovery
```typescript
async function recoverSession(sessionId: string): Promise<void> {
  // Send ResendRequest to recover missed messages
  const lastSeqNum = await getLastProcessedSeqNum(sessionId);
  const resendMsg = buildResendRequest(lastSeqNum + 1);
  await send(resendMsg);
}

async function handleGapFill(gapFillMsg: string): Promise<void> {
  // Process gap fill message
  const newSeqNum = extractSeqNum(gapFillMsg);
  await updateSeqNum(newSeqNum);
}
```

### Circuit Breaker
```typescript
class FIXCircuitBreaker {
  private failureCount = 0;
  private state: "closed" | "open" | "half-open" = "closed";
  private readonly threshold = 5;
  private readonly timeout = 60000; // 1 minute

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === "open") {
      throw new Error("Circuit breaker is open");
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess(): void {
    this.failureCount = 0;
    this.state = "closed";
  }

  private onFailure(): void {
    this.failureCount++;
    if (this.failureCount >= this.threshold) {
      this.state = "open";
      setTimeout(() => {
        this.state = "half-open";
      }, this.timeout);
    }
  }
}
```

## Testing

### FIX Simulator
```bash
# Use QuickFIX simulator for testing
docker run -p 5001:5001 \
  quickfixgo/quickfix \
  -config=/config/acceptor.cfg
```

### Test Cases
1. Successful order placement and fill
2. Partial fill scenarios
3. Order cancellation
4. Order rejection
5. Session disconnect and recovery
6. Sequence number gap handling

## Monitoring

```typescript
// FIX session metrics
interface FIXMetrics {
  messagesIn: number;
  messagesOut: number;
  heartbeatsMissed: number;
  ordersPlaced: number;
  ordersFilled: number;
  ordersRejected: number;
  latencyMs: number;
}

async function reportFIXMetrics(metrics: FIXMetrics): Promise<void> {
  // Send to monitoring system (Prometheus, CloudWatch, etc.)
}
```

## Compliance & Audit

- All FIX messages logged (incoming/outgoing)
- Checksums validated on every message
- Sequence numbers must be continuous
- Session logs retained for 7 years
- Pre-trade risk checks (credit limits, position limits)

## Integration Checklist

- [ ] FIX credentials obtained from broker
- [ ] Network connectivity established (VPN/private link)
- [ ] FIX session tested in broker UAT environment
- [ ] Order state machine implemented
- [ ] Execution reports handled correctly
- [ ] Circuit breaker and retry logic in place
- [ ] Monitoring and alerting configured
- [ ] Audit logging enabled for all FIX traffic
- [ ] Disaster recovery tested (session recovery)
- [ ] Production certification completed with broker
