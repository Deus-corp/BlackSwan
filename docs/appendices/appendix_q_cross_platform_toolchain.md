# Appendix Q: Cross-Platform Toolchain & Hardware-Rooted Entanglement

**Назначение:** Описать инструментарий, обеспечивающий гетерогенность роя на уровне операционных систем и аппаратных архитектур, а также механизм аппаратной привязки Core DNA с использованием Physical Unclonable Functions (PUF). Детали реализации кросс-компиляции, профилей персистентности под Windows/macOS/Linux и код PUF-провайдера вынесены в данный Appendix.

---

## Q.1. Актуальный артефакт

| Поле | Значение |
| :--- | :--- |
| **CID (IPFS)** | `QmCrossPlatformToolingV1` |
| **BLAKE3 хеш** | `e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0` |
| **Имя файла** | `cross_platform_manifest.json` |
| **Версия** | 1.0 |
| **Дата** | 2026-04-20T12:00:00Z |

---

## Q.2. Стек сборки (Reproducible Multi‑OS Build)

Для обеспечения «биологического разнообразия» роя и защиты от платформенных уязвимостей используется унифицированный сборочный стек, позволяющий компилировать компоненты под различные целевые платформы из единого Linux-окружения.

- **Zig CC** — кросс-компилятор для C/C++ зависимостей. Позволяет собирать нативный код под Windows (MSVC) и macOS (Mach-O) без необходимости в целевых SDK.
- **Cargo-zigbuild** — расширение для Cargo, использующее Zig в качестве линкера. Обеспечивает сборку Rust-компонентов (системные демоны, утилиты) под все поддерживаемые ОС.

Конфигурация вызова:
```bash
cargo zigbuild --release --target x86_64-pc-windows-msvc
cargo zigbuild --release --target aarch64-apple-darwin
```

---

## Q.3. Polymorphic OS Presence

Для маскировки под нативные процессы каждой ОС используются специфичные техники закрепления и обфускации. Детали реализации приведены в доменном модуле Hardware_Independence_HAEL.md (раздел 3).

· Windows Persistence: регистрация как критической службы (SCM), техники Process Ghosting и Herpaderping, маскировка под svchost.exe.
· macOS Persistence: использование launchd, System Extensions, подпись Mach-O синтетическими сертификатами из Persona Farm.
· Linux Persistence: systemd-сервисы, маскировка под легитимных демонов (например, systemd-journald).

---

## Q.4. Библиотека hardware_lock.rs (PUF Provider)

Ключевой компонент, реализующий аппаратную привязку Core DNA. Извлекает энтропию из физических характеристик кремния и использует её для генерации ключа дешифровки.

```rust
// security/src/puf_provider.rs
pub struct HardwareLock;

impl HardwareLock {
    /// Генерирует уникальный seed на основе физических дефектов кремния
    pub fn get_puf_seed() -> [u8; 32] {
        #[cfg(target_arch = "x86_64")]
        {
            let entropy = measure_clock_jitter();
            let cpu_id = get_cpuid_leaf();
            combine_to_seed(entropy, cpu_id)
        }
        // Аналогичные реализации для ARM, Apple Silicon и т.д.
    }

    /// Расшифровывает Core DNA с использованием PUF-энтропии и доли Шамира
    pub fn decrypt_core_dna(
        encrypted_data: Vec<u8>,
        shamir_share: [u8; 32],
    ) -> Result<Vec<u8>, AuthError> {
        let puf_seed = Self::get_puf_seed();
        let final_key = xor_keys(shamir_share, puf_seed);
        aes_256_gcm_decrypt(encrypted_data, final_key)
    }
}
```

Полный исходный код PUF-провайдера включён в workspace QmCoreToolsWorkspaceV2 (крейт security). Процедура регистрации PUF при первом холодном старте описана в Hardware_Isolation.md.

---

## Q.5. Связь с другими разделами

· Polymorphic OS Presence: Hardware_Independence_HAEL.md
· Hardware-Rooted Entanglement (Spore 2.0): Spore_Protocol_and_Recovery.md
· Tooling for AST Integrity and TDE: Appendix_O_Tooling_AST_Integrity.md (по готовности)
· Глоссарий: Glossary.md