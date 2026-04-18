# 📊 Clarity Contract Analysis: `amm`

## 📋 Summary

| Component | Count |
|---|---|
| Traits used | 1 |
| Constants | 3 |
| Errors | 9 |
| Maps | 2 |
| Data Vars | 0 |
| Tokens | 0 |
| Public functions | 1 |
| Read-only functions | 2 |
| Private functions | 1 |

## 🏗️ Architecture

> Funciones, storage, traits y relaciones entre ellos.

```mermaid
graph LR
  subgraph TRAITS[🔗 Traits]
    trait_ft_trait([ft-trait])
  end
  subgraph STORAGE[💾 Storage]
    map_pools[(🗺 pools)]
    map_positions[(🗺 positions)]
  end
  subgraph CONSTS[📌 Constants & Errors]
    const_MINIMUM_LIQUIDITY[MINIMUM_LIQUIDITY]:::constStyle
    const_THIS_CONTRACT[THIS_CONTRACT]:::constStyle
    const_FEES_DENOM[FEES_DENOM]:::constStyle
    err_ERR_POOL_ALREADY_EXISTS[ERR_POOL_ALREADY_EXISTS]:::errStyle
    err_ERR_INCORRECT_TOKEN_ORDERING[ERR_INCORRECT_TOKEN_ORDERING]:::errStyle
    err_ERR_INSUFFICIENT_LIQUIDITY_MINTED[ERR_INSUFFICIENT_LIQUIDITY_MINTED]:::errStyle
    err_ERR_INSUFFICIENT_LIQUIDITY_OWNED[ERR_INSUFFICIENT_LIQUIDITY_OWNED]:::errStyle
    err_ERR_INSUFFICIENT_LIQUIDITY_BURNED[ERR_INSUFFICIENT_LIQUIDITY_BURNED]:::errStyle
    err_ERR_INSUFFICIENT_INPUT_AMOUNT[ERR_INSUFFICIENT_INPUT_AMOUNT]:::errStyle
    err_ERR_INSUFFICIENT_LIQUIDITY_FOR_SWAP[ERR_INSUFFICIENT_LIQUIDITY_FOR_SWAP]:::errStyle
    err_ERR_INSUFFICIENT_1_AMOUNT[ERR_INSUFFICIENT_1_AMOUNT]:::errStyle
    err_ERR_INSUFFICIENT_0_AMOUNT[ERR_INSUFFICIENT_0_AMOUNT]:::errStyle
  end
  subgraph FUNCS[⚙️ Functions]
    fn_get_pool_id([get-pool-id]):::read_onlyStyle
    fn_correct_token_ordering[/correct-token-ordering/]:::privateStyle
    fn_create_pool[[create-pool]]:::publicStyle
    fn_get_position_liquidity([get-position-liquidity]):::read_onlyStyle
  end
  fn_correct_token_ordering -. throws .-> err_ERR_INCORRECT_TOKEN_ORDERING
  map_pools -. read .-> fn_create_pool
  fn_create_pool -- write --> map_pools
  fn_create_pool --> fn_correct_token_ordering
  fn_create_pool --> fn_get_pool_id
  fn_create_pool -. throws .-> err_ERR_POOL_ALREADY_EXISTS
  fn_create_pool -. throws .-> err_ERR_INCORRECT_TOKEN_ORDERING
  map_positions -. read .-> fn_get_position_liquidity
  classDef publicStyle fill:#4CAF50,color:#fff,stroke:#388E3C
  classDef read_onlyStyle fill:#2196F3,color:#fff,stroke:#1565C0
  classDef privateStyle fill:#FF9800,color:#fff,stroke:#E65100
  classDef errStyle fill:#F44336,color:#fff,stroke:#B71C1C
  classDef constStyle fill:#607D8B,color:#fff,stroke:#37474F
  classDef varStyle fill:#E91E63,color:#fff,stroke:#880E4F
  classDef tokenStyle fill:#FF5722,color:#fff,stroke:#BF360C
```

## 📞 Call Graph

```mermaid
graph TD
  fn_get_pool_id([get-pool-id]):::read_onlyStyle
  fn_correct_token_ordering[/correct-token-ordering/]:::privateStyle
  fn_create_pool[[create-pool]]:::publicStyle
  fn_get_position_liquidity([get-position-liquidity]):::read_onlyStyle
  fn_create_pool --> fn_correct_token_ordering
  fn_create_pool --> fn_get_pool_id
  classDef publicStyle fill:#4CAF50,color:#fff
  classDef read_onlyStyle fill:#2196F3,color:#fff
  classDef privateStyle fill:#FF9800,color:#fff
```

## 🔄 Data Flow

> Accesos de lectura/escritura al storage.

```mermaid
graph LR
  map_pools[(🗺 pools)]
  map_positions[(🗺 positions)]
  fn_create_pool[[create-pool]]:::publicStyle
  map_pools -. read .-> fn_create_pool
  fn_create_pool -- write --> map_pools
  fn_get_position_liquidity([get-position-liquidity]):::read_onlyStyle
  map_positions -. read .-> fn_get_position_liquidity
  classDef publicStyle fill:#4CAF50,color:#fff
  classDef read_onlyStyle fill:#2196F3,color:#fff
  classDef privateStyle fill:#FF9800,color:#fff
```

## 🗺️ Storage Schema

```mermaid
classDiagram
  class poolsMAP {
    <<map>>
    KEY: (buff 20)
    VALUE: ?
  }
  class positionsMAP {
    <<map>>
    KEY: (buff 20)
    VALUE: ?
  }
```

## ❌ Error Paths

```mermaid
graph LR
  err_ERR_POOL_ALREADY_EXISTS[❌ ERR_POOL_ALREADY_EXISTS]:::errStyle
  err_ERR_INCORRECT_TOKEN_ORDERING[❌ ERR_INCORRECT_TOKEN_ORDERING]:::errStyle
  err_ERR_INSUFFICIENT_LIQUIDITY_MINTED[❌ ERR_INSUFFICIENT_LIQUIDITY_MINTED]:::errStyle
  err_ERR_INSUFFICIENT_LIQUIDITY_OWNED[❌ ERR_INSUFFICIENT_LIQUIDITY_OWNED]:::errStyle
  err_ERR_INSUFFICIENT_LIQUIDITY_BURNED[❌ ERR_INSUFFICIENT_LIQUIDITY_BURNED]:::errStyle
  err_ERR_INSUFFICIENT_INPUT_AMOUNT[❌ ERR_INSUFFICIENT_INPUT_AMOUNT]:::errStyle
  err_ERR_INSUFFICIENT_LIQUIDITY_FOR_SWAP[❌ ERR_INSUFFICIENT_LIQUIDITY_FOR_SWAP]:::errStyle
  err_ERR_INSUFFICIENT_1_AMOUNT[❌ ERR_INSUFFICIENT_1_AMOUNT]:::errStyle
  err_ERR_INSUFFICIENT_0_AMOUNT[❌ ERR_INSUFFICIENT_0_AMOUNT]:::errStyle
  fn_correct_token_ordering[/correct-token-ordering/]:::privateStyle
  fn_correct_token_ordering -- asserts --> err_ERR_INCORRECT_TOKEN_ORDERING
  fn_create_pool[[create-pool]]:::publicStyle
  fn_create_pool -- asserts --> err_ERR_POOL_ALREADY_EXISTS
  fn_create_pool -- asserts --> err_ERR_INCORRECT_TOKEN_ORDERING
  classDef publicStyle fill:#4CAF50,color:#fff
  classDef read_onlyStyle fill:#2196F3,color:#fff
  classDef privateStyle fill:#FF9800,color:#fff
  classDef errStyle fill:#F44336,color:#fff
```

## ⚙️ Function Details

| Function | Type | Params | Map R | Map W | Var R | Var W | Asserts | Calls |
|---|---|---|---|---|---|---|---|---|
| `get-pool-id` | read-only | — | — | — | — | — | 0 | pool-id, buff, pool-info |
| `correct-token-ordering` | private | — | — | — | — | — | 1 | token-0, token-0-buff, token-1, token-1-buff |
| `create-pool` | public | — | pools | pools | — | — | 2 | correct-token-ordering, pool-does-not-exist, pool-id, fee, token-1-principal, pool-info, token-1, token-0-principal, pool-data, token-0, get-pool-id |
| `get-position-liquidity` | read-only | — | positions | — | — | — | 0 | pool-id, buff, position, existing-owner-liquidity, owner |

## 🔗 Traits

- `ft-trait` → `'SP3FBR2AGK5H9QBDH3EEN6DF8EK8JY7RX8QJ5SVTE.sip-010-trait-ft-standard.sip-010-trait)`
