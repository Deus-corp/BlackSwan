# Appendix AC — Nostr Bridge Specification (EventBus over Nostr)
## AC.1. Назначение
Полная спецификация демона `nostr-bridge-d`, обеспечивающего прозрачную интеграцию локальной EventBus с децентрализованной сетью Nostr.
## AC.2. Реализация на Rust (nostr-sdk 0.33)
```rust
// Cargo.toml
[dependencies]
Nostr-sdk = { version = «0.33», features = [«nip44», «socks»] }
Tokio = { version = «1.0», features = [«full»] }
Serde = { version = «1.0», features = [«derive»] }
Serde_json = «1.0»
Log = «0.4»
// main.rs (фрагмент)
Use nostr_sdk::prelude::*;
Use std::str::FromStr;
Pub struct NostrBridge {
Client: Client,
Identity: Keys,
Local_rx: tokio::sync::broadcast::Receiver<InternalEvent>,
}
Impl NostrBridge {
Pub async fn new(secret_key: &str, relays: Vec<String>, local_rx: …) -> Result<Self> {
Let identity = Keys::from_sk_str(secret_key)?;
Let proxy = std::net::SocketAddr::from_str(«127.0.0.1:9050»)?;
Let opts = Options::new().proxy(proxy).wait_for_send(true);
Let client = Client::with_opts(&identity, opts);
For relay in relays {
Client.add_relay(relay).await?;
}
Client.connect().await;
Ok(Self { client, identity, local_rx })
}
Async fn broadcast_to_nostr(&self, event: InternalEvent) -> Result<()> {
Let kind = match event.topic.as_str() {
«economic» => Kind::Custom(20001),
«security» => Kind::Custom(20002),
«infra» => Kind::Custom(20003),
«command» => Kind::Custom(20000),
_ => Kind::Custom(20003),
};
Let payload = serde_json::to_string(&event.payload)?;
Let encrypted = nip44::encrypt(
&self.identity.secret_key()?,
&receiver_pubkey, // из конфигурации
Payload,
Nip44::Version::V2,
)?;
Let nostr_event = EventBuilder::new(kind, encrypted, [])
.to_event(&self.identity)?;
Self.client.send_event(nostr_event).await?;
Ok(())
}
}
```
## AC.3. Пример инкапсуляции события
…
## AC.4. Развёртывание скрытого .onion‑реле
…
