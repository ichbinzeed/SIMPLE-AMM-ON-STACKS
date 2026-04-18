import {
  isConnected,
  getLocalStorage,
  connect,
  disconnect,
  openContractCall,
} from "@stacks/connect";
import {
  contractPrincipalCV,
  cvToJSON,
  fetchCallReadOnlyFunction,
  Pc,
  PostConditionMode,
  principalCV,
  tupleCV,
  uintCV,
} from "@stacks/transactions";

const btnConnect = document.getElementById("btn-connect");
const btnLogout = document.getElementById("btn-logout");
const addressInput = document.getElementById("addressInput");
const mintOneBtn = document.getElementById("mintOne");
const mintTwoBtn = document.getElementById("mintTwo");
const refreshBtn = document.getElementById("refreshBalances");
const mock1Element = document.getElementById("mock1");
const mock2Element = document.getElementById("mock2");
const mintStatusElement = document.getElementById("mintStatus");
const poolsListElement = document.getElementById("poolsList");
const eventsListElement = document.getElementById("eventsList");
const createToken0Input = document.getElementById("createToken0");
const createToken1Input = document.getElementById("createToken1");
const createPoolFeeInput = document.getElementById("createPoolFee");
const createPoolBtn = document.getElementById("createPoolBtn");
const liquidityPoolSelect = document.getElementById("liquidityPoolSelect");
const amount0DesiredInput = document.getElementById("amount0Desired");
const amount1DesiredInput = document.getElementById("amount1Desired");
const amount0MinInput = document.getElementById("amount0Min");
const amount1MinInput = document.getElementById("amount1Min");
const addLiquidityBtn = document.getElementById("addLiquidityBtn");

const contractAddress = "ST1KQYEWGK8023G55G9JHSH8A3YHP3RNX6JJY1F9Q";
const ammContractName = "AMM";
const ammContractId = `${contractAddress}.${ammContractName}`;
const tokenContracts = {
  mock1: {
    address: contractAddress,
    contractName: "mock-token",
    assetName: "mock-token",
  },
  mock2: {
    address: contractAddress,
    contractName: "mock-token-2",
    assetName: "mock-token",
  },
};
const SEEDED_POOLS = [
  {
    poolId: "0x40b265759ed82544798f0fd6daa167cff6a95f6c",
    fee: 500,
    token0: {
      address: contractAddress,
      contractName: "mock-token",
      full: `${contractAddress}.mock-token`,
    },
    token1: {
      address: contractAddress,
      contractName: "mock-token-2",
      full: `${contractAddress}.mock-token-2`,
    },
    createdTxId:
      "0x15515c3d785d10c90eb4bb31a1d7b408b8dab6de3083cb59de6ff9a4b8b75f7c",
  },
];
const HIRO_TESTNET_API = `${window.location.origin}/api`;
const TOKEN_SCALE = 1000000n;
const MINT_AMOUNT = 1000000;
const POOL_HISTORY_PAGE_SIZE = 50;
const EMPTY_POOL_ID = "0x0000000000000000000000000000000000000000";

const balances = {
  mock1: "0",
  mock2: "0",
};

let knownPools = [];
let refreshIntervalId = null;
let txInFlight = false;
let pendingTxId = null;
let pendingActionLabel = "";

function getUserAddress() {
  const userData = getLocalStorage();
  return userData?.addresses?.stx?.[0]?.address ?? null;
}

function parseUintInput(element, fallback = 0) {
  const value = Number.parseInt(element?.value ?? "", 10);
  return Number.isFinite(value) && value >= 0 ? value : fallback;
}

function inferAssetName(contractName) {
  if (String(contractName).startsWith("mock-token")) {
    return "mock-token";
  }

  return contractName;
}

function parseContractPrincipal(input) {
  const normalized = String(input ?? "")
    .trim()
    .replace(/^'/, "");
  const [address, ...nameParts] = normalized.split(".");

  if (!address || !nameParts.length) {
    throw new Error(
      "Usa el formato completo ST...nombre-del-contrato para el token.",
    );
  }

  const contractName = nameParts.join(".");
  return {
    address,
    contractName,
    assetName: inferAssetName(contractName),
    full: `${address}.${contractName}`,
  };
}

function normalizePoolTokens(tokenA, tokenB) {
  return [tokenA, tokenB].sort((left, right) =>
    left.full.localeCompare(right.full),
  );
}

function tokenToCV(token) {
  return contractPrincipalCV(token.address, token.contractName);
}

function buildTokenPostCondition(token, amount, address = getUserAddress()) {
  if (!token || !address || amount <= 0) return null;

  return Pc.principal(address)
    .willSendLte(BigInt(amount))
    .ft(
      `${token.address}.${token.contractName}`,
      token.assetName ?? inferAssetName(token.contractName),
    );
}

function getPoolInfoTuple(token0, token1, fee) {
  return tupleCV({
    "token-0": tokenToCV(token0),
    "token-1": tokenToCV(token1),
    fee: uintCV(fee),
  });
}

function formatTokenAmount(rawAmount) {
  const amount = BigInt(rawAmount ?? 0);
  const whole = amount / TOKEN_SCALE;
  const fractional = amount % TOKEN_SCALE;

  if (fractional === 0n) return whole.toString();

  return `${whole}.${fractional.toString().padStart(6, "0").replace(/0+$/, "")}`;
}

function formatLiquidityAmount(rawAmount) {
  const amount = BigInt(rawAmount ?? 0);
  const whole = amount / TOKEN_SCALE;
  const fractional = amount % TOKEN_SCALE;

  return `${whole}.${fractional.toString().padStart(6, "0")}`;
}

function shortenValue(value) {
  if (!value) return "-";
  return value.length <= 18
    ? value
    : `${value.slice(0, 10)}...${value.slice(-6)}`;
}

function getDisplayTokenName(contractId) {
  return (
    String(contractId ?? "")
      .split(".")
      .slice(1)
      .join(".") || contractId
  );
}

function getPoolLabel(pool) {
  return `${getDisplayTokenName(pool.token0.full)} / ${getDisplayTokenName(pool.token1.full)}`;
}

function setStatus(message) {
  if (mintStatusElement) {
    mintStatusElement.textContent = message;
  }
}

function setActionButtonsDisabled(disabled) {
  [mintOneBtn, mintTwoBtn, createPoolBtn, addLiquidityBtn].forEach((button) => {
    if (button) button.disabled = disabled;
  });
}

function renderMockBalances() {
  if (mock1Element) mock1Element.textContent = balances.mock1;
  if (mock2Element) mock2Element.textContent = balances.mock2;
}

function setMockBalance(tokenId, amount) {
  if (!(tokenId in balances)) return;
  balances[tokenId] = formatTokenAmount(amount);
  renderMockBalances();
}

function renderPoolSelect(pools = knownPools) {
  if (!liquidityPoolSelect) return;

  if (!pools.length) {
    liquidityPoolSelect.innerHTML =
      '<option value="">No hay pools detectadas</option>';
    return;
  }

  liquidityPoolSelect.innerHTML = pools
    .map((pool) => {
      const value = encodeURIComponent(
        JSON.stringify({
          token0: pool.token0.full,
          token1: pool.token1.full,
          fee: pool.fee,
        }),
      );
      return `<option value="${value}">${getPoolLabel(pool)} · fee ${pool.fee}</option>`;
    })
    .join("");
}

function renderPools(pools) {
  if (!poolsListElement) return;

  if (!pools.length) {
    poolsListElement.innerHTML = `
      <p class="empty-state">
        No hay pools detectadas todavía en el contrato desplegado.
      </p>
    `;
    return;
  }

  poolsListElement.innerHTML = pools
    .map(
      (pool) => `
        <article class="pool-card">
          <div class="pool-top">
            <div>
              <span class="pill">Fee ${pool.fee}</span>
              <h3>${getPoolLabel(pool)}</h3>
            </div>
            <span class="pool-id">${shortenValue(pool.poolId)}</span>
          </div>

          <div class="pool-stats">
            <div>
              <span>Reserva ${getDisplayTokenName(pool.token0.full)}</span>
              <strong>${pool.balance0Formatted}</strong>
            </div>
            <div>
              <span>Reserva ${getDisplayTokenName(pool.token1.full)}</span>
              <strong>${pool.balance1Formatted}</strong>
            </div>
            <div>
              <span>Liquidez total</span>
              <strong>${pool.totalLiquidity}</strong>
            </div>
            <div>
              <span>Tu liquidez</span>
              <strong>${pool.userLiquidity}</strong>
            </div>
          </div>
        </article>
      `,
    )
    .join("");
}

function parseEventAction(repr) {
  const match = String(repr ?? "").match(/action:\s*"([^"]+)"/i);
  return match?.[1] ?? "evento";
}

function renderEvents(events) {
  if (!eventsListElement) return;

  if (!events.length) {
    eventsListElement.innerHTML = `
      <p class="empty-state">No hay eventos recientes para mostrar.</p>
    `;
    return;
  }

  eventsListElement.innerHTML = events
    .map(
      (event) => `
        <article class="pool-card">
          <div class="pool-top">
            <div>
              <span class="pill">${event.action}</span>
              <h3>${event.txIdShort}</h3>
            </div>
          </div>
          <div class="pool-stats">
            <div>
              <span>Contenido</span>
              <strong>${event.repr}</strong>
            </div>
          </div>
        </article>
      `,
    )
    .join("");
}

async function callReadonly(contractName, functionName, functionArgs, sender) {
  return fetchCallReadOnlyFunction({
    contractAddress,
    contractName,
    functionName,
    functionArgs,
    senderAddress: sender ?? getUserAddress() ?? contractAddress,
    client: { baseUrl: HIRO_TESTNET_API },
  });
}

async function fetchTransactionStatus(txId) {
  try {
    const response = await fetch(`${HIRO_TESTNET_API}/extended/v1/tx/${txId}`);
    if (!response.ok) return null;

    const data = await response.json();
    return data.tx_status ?? data.status ?? null;
  } catch (error) {
    console.error("Error consultando el estado de la transacción:", error);
    return null;
  }
}

async function fetchPoolHistory() {
  const allTransactions = [];
  let offset = 0;
  let total = 0;

  do {
    const response = await fetch(
      `${HIRO_TESTNET_API}/extended/v1/address/${encodeURIComponent(ammContractId)}/transactions?limit=${POOL_HISTORY_PAGE_SIZE}&offset=${offset}`,
    );

    if (!response.ok) {
      throw new Error(
        `No se pudo leer el historial del contrato: ${response.status}`,
      );
    }

    const data = await response.json();
    const batch = Array.isArray(data.results) ? data.results : [];

    total = data.total ?? batch.length;
    allTransactions.push(...batch);
    offset += batch.length;

    if (!batch.length) break;
  } while (offset < total);

  return allTransactions;
}

async function fetchRecentEvents() {
  try {
    const transactions = await fetchPoolHistory();
    const recent = transactions.slice(0, 8);
    const details = await Promise.all(
      recent.map(async (tx) => {
        const response = await fetch(
          `${HIRO_TESTNET_API}/extended/v1/tx/${tx.tx_id}`,
        );
        if (!response.ok) return [];

        const data = await response.json();
        const events = Array.isArray(data.events) ? data.events : [];

        return events
          .filter((event) => event.event_type === "smart_contract_log")
          .filter((event) => event.contract_log?.contract_id === ammContractId)
          .map((event) => ({
            action: parseEventAction(event.contract_log?.value?.repr),
            repr: event.contract_log?.value?.repr ?? "Sin contenido",
            txIdShort: shortenValue(tx.tx_id),
          }));
      }),
    );

    renderEvents(details.flat());
  } catch (error) {
    console.error("Error cargando eventos del contrato:", error);
    renderEvents([]);
  }
}

function mergeUniquePools(...groups) {
  const uniquePools = new Map();

  groups.flat().forEach((pool) => {
    if (!pool?.token0?.full || !pool?.token1?.full) return;
    const key = `${pool.token0.full}|${pool.token1.full}|${pool.fee}`;
    uniquePools.set(key, pool);
  });

  return [...uniquePools.values()];
}

function extractPoolsFromTransactions(transactions) {
  const uniquePools = new Map();

  transactions
    .filter(
      (tx) =>
        tx.tx_status === "success" &&
        tx.tx_type === "contract_call" &&
        tx.contract_call?.function_name === "create-pool",
    )
    .forEach((tx) => {
      const args = tx.contract_call?.function_args ?? [];
      const token0Repr = args
        .find((arg) => arg.name === "token-0")
        ?.repr?.replace(/^'/, "");
      const token1Repr = args
        .find((arg) => arg.name === "token-1")
        ?.repr?.replace(/^'/, "");
      const feeRepr = args.find((arg) => arg.name === "fee")?.repr ?? "u0";
      const fee = Number.parseInt(feeRepr.replace(/^u/, ""), 10);

      if (!token0Repr || !token1Repr || !Number.isFinite(fee)) return;

      const [token0, token1] = normalizePoolTokens(
        parseContractPrincipal(token0Repr),
        parseContractPrincipal(token1Repr),
      );
      const key = `${token0.full}|${token1.full}|${fee}`;

      if (!uniquePools.has(key)) {
        uniquePools.set(key, {
          token0,
          token1,
          fee,
          createdTxId: tx.tx_id,
        });
      }
    });

  return [...uniquePools.values()];
}

function clearPendingTx(message) {
  txInFlight = false;
  pendingTxId = null;
  pendingActionLabel = "";
  setActionButtonsDisabled(false);
  setStatus(message);
}

async function refreshTokenBalance(
  tokenId,
  tokenConfig,
  address = getUserAddress(),
) {
  if (!address) {
    setMockBalance(tokenId, 0);
    return;
  }

  try {
    const result = await callReadonly(
      tokenConfig.contractName,
      "get-balance",
      [principalCV(address)],
      address,
    );

    const json = cvToJSON(result);
    setMockBalance(tokenId, json?.value?.value ?? 0);
  } catch (error) {
    console.error(
      `Error leyendo balance de ${tokenConfig.contractName}:`,
      error,
    );
    setMockBalance(tokenId, 0);
  }
}

async function fetchPoolState(pool, address = getUserAddress()) {
  const senderAddress = address ?? contractAddress;

  try {
    const poolIdCV = await callReadonly(
      ammContractName,
      "get-pool-id",
      [getPoolInfoTuple(pool.token0, pool.token1, pool.fee)],
      senderAddress,
    );
    const poolIdJson = cvToJSON(poolIdCV);

    const poolDataCV = await callReadonly(
      ammContractName,
      "get-pool-data",
      [poolIdCV],
      senderAddress,
    );
    const poolDataJson = cvToJSON(poolDataCV);
    const poolTuple = poolDataJson?.value?.value?.value;

    let userLiquidity = "—";
    if (address) {
      const userLiquidityCV = await callReadonly(
        ammContractName,
        "get-position-liquidity",
        [poolIdCV, principalCV(address)],
        senderAddress,
      );
      const userLiquidityJson = cvToJSON(userLiquidityCV);
      userLiquidity = userLiquidityJson?.value?.value ?? "0";
    }

    return {
      ...pool,
      poolId: poolIdJson?.value ?? pool.createdTxId,
      totalLiquidity: formatLiquidityAmount(poolTuple?.liquidity?.value ?? 0),
      userLiquidity: address ? formatLiquidityAmount(userLiquidity) : "—",
      balance0Formatted: formatTokenAmount(
        poolTuple?.["balance-0"]?.value ?? 0,
      ),
      balance1Formatted: formatTokenAmount(
        poolTuple?.["balance-1"]?.value ?? 0,
      ),
    };
  } catch (error) {
    console.error(
      `Error leyendo estado de la pool ${getPoolLabel(pool)}:`,
      error,
    );
    return {
      ...pool,
      poolId: pool.createdTxId,
      totalLiquidity: formatLiquidityAmount(0),
      userLiquidity: address ? formatLiquidityAmount(0) : "—",
      balance0Formatted: "0",
      balance1Formatted: "0",
    };
  }
}

async function syncPendingTxStatus(address = getUserAddress()) {
  if (!pendingTxId || !address) return;

  const txStatus = await fetchTransactionStatus(pendingTxId);

  if (txStatus === "success") {
    clearPendingTx(`${pendingActionLabel || "Transacción"} confirmada.`);
    return;
  }

  if (txStatus && (txStatus.startsWith("abort") || txStatus === "failed")) {
    clearPendingTx(`${pendingActionLabel || "Transacción"} falló: ${txStatus}`);
    return;
  }

  setStatus(
    `${pendingActionLabel || "Transacción"} pendiente. Esperando confirmación...`,
  );
}

async function refreshMockBalances(
  address = getUserAddress(),
  { skipPendingSync = false } = {},
) {
  if (!address) {
    setMockBalance("mock1", 0);
    setMockBalance("mock2", 0);
    setStatus("Conecta la wallet para ver tus balances y tus pools.");
    return;
  }

  if (!skipPendingSync) {
    await syncPendingTxStatus(address);
  }

  await Promise.all([
    refreshTokenBalance("mock1", tokenContracts.mock1, address),
    refreshTokenBalance("mock2", tokenContracts.mock2, address),
  ]);

  if (!pendingTxId) {
    setStatus("Balances actualizados.");
  }
}

async function fetchPoolsFromContractIndex(address = getUserAddress()) {
  const senderAddress = address ?? contractAddress;

  const countCV = await callReadonly(
    ammContractName,
    "get-pool-count",
    [],
    senderAddress,
  );
  const countJson = cvToJSON(countCV);
  const poolCount = Number.parseInt(countJson?.value ?? "0", 10);

  if (!Number.isFinite(poolCount) || poolCount <= 0) {
    return [];
  }

  const pools = [];

  for (let index = 0; index < poolCount; index += 1) {
    const poolIdCV = await callReadonly(
      ammContractName,
      "get-pool-id-by-index",
      [uintCV(index)],
      senderAddress,
    );
    const poolIdJson = cvToJSON(poolIdCV);
    const poolId = poolIdJson?.value;

    if (!poolId || poolId === EMPTY_POOL_ID) continue;

    const poolDataCV = await callReadonly(
      ammContractName,
      "get-pool-data",
      [poolIdCV],
      senderAddress,
    );
    const poolDataJson = cvToJSON(poolDataCV);
    const tuple = poolDataJson?.value?.value?.value;

    if (!tuple?.["token-0"]?.value || !tuple?.["token-1"]?.value) continue;

    pools.push({
      poolId,
      fee: Number.parseInt(tuple.fee?.value ?? "0", 10),
      token0: parseContractPrincipal(tuple["token-0"]?.value),
      token1: parseContractPrincipal(tuple["token-1"]?.value),
      createdTxId: poolId,
    });
  }

  return pools;
}

async function loadPools(address = getUserAddress()) {
  if (poolsListElement) {
    poolsListElement.innerHTML = '<p class="empty-state">Cargando pools...</p>';
  }

  try {
    let discoveredPools = [...SEEDED_POOLS];

    try {
      const indexedPools = await fetchPoolsFromContractIndex(address);
      discoveredPools = mergeUniquePools(discoveredPools, indexedPools);
    } catch {
      // el contrato desplegado actual no tiene índice; mantenemos la pool conocida
    }

    try {
      const transactions = await fetchPoolHistory();
      discoveredPools = mergeUniquePools(
        discoveredPools,
        extractPoolsFromTransactions(transactions),
      );
    } catch {
      // si falla el historial, seguimos mostrando la pool copiada manualmente
    }

    const hydratedPools = await Promise.all(
      discoveredPools.map((pool) => fetchPoolState(pool, address)),
    );

    knownPools = hydratedPools.sort((left, right) => left.fee - right.fee);
    renderPools(knownPools);
    renderPoolSelect(knownPools);
  } catch (error) {
    console.error("Error cargando las pools del contrato desplegado:", error);
    knownPools = [...SEEDED_POOLS];
    renderPools(knownPools);
    renderPoolSelect(knownPools);
  }
}

async function refreshAllData(address = getUserAddress()) {
  if (address && pendingTxId) {
    await syncPendingTxStatus(address);
  }

  await Promise.all([
    refreshMockBalances(address, { skipPendingSync: true }),
    loadPools(address),
    fetchRecentEvents(),
  ]);
}

function updateUI() {
  const authenticated = isConnected();

  if (authenticated) {
    btnConnect.style.display = "none";
    btnLogout.style.display = "inline";

    const userAddress = getUserAddress();
    addressInput.textContent = userAddress ?? "Disconnected";
    startAutoRefresh(userAddress);
  } else {
    btnConnect.style.display = "inline";
    btnLogout.style.display = "none";
    addressInput.textContent = "Disconnected";
    stopAutoRefresh();
    clearPendingTx("Conecta la wallet para ver tus balances y tus pools.");
    setMockBalance("mock1", 0);
    setMockBalance("mock2", 0);
  }
}

function startAutoRefresh(address = getUserAddress()) {
  stopAutoRefresh();

  if (!address) return;

  refreshIntervalId = window.setInterval(() => {
    refreshAllData(address);
  }, 15000);
}

function stopAutoRefresh() {
  if (refreshIntervalId) {
    window.clearInterval(refreshIntervalId);
    refreshIntervalId = null;
  }
}

function watchSubmittedTx(txId, userAddress, actionLabel) {
  txInFlight = false;
  pendingTxId = txId;
  pendingActionLabel = actionLabel;
  setStatus(`${actionLabel} enviada. Esperando confirmación...`);

  const poll = async () => {
    await syncPendingTxStatus(userAddress);

    if (pendingTxId === txId) {
      window.setTimeout(poll, 5000);
    } else {
      await refreshAllData(userAddress);
    }
  };

  window.setTimeout(poll, 5000);
}

async function startContractAction({
  contractName,
  functionName,
  functionArgs,
  postConditions = [],
  postConditionMode = PostConditionMode.Deny,
  actionLabel,
  onSubmitted,
}) {
  const userAddress = getUserAddress();

  if (!userAddress) {
    alert("Conecta tu wallet primero.");
    return;
  }

  if (txInFlight || pendingTxId) {
    alert(
      "Ya hay una transacción pendiente. Espera la confirmación para evitar problemas de nonce.",
    );
    return;
  }

  try {
    txInFlight = true;
    setActionButtonsDisabled(true);
    setStatus(`Abriendo wallet para ${actionLabel}...`);

    await openContractCall({
      contractAddress,
      contractName,
      functionName,
      functionArgs,
      postConditions,
      postConditionMode,
      appDetails: {
        name: "AMM",
        icon: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Ctext y='0.9em' font-size='90'%3E🪙%3C/text%3E%3C/svg%3E",
      },
      onFinish: ({ txId }) => {
        console.log(`${actionLabel} enviada. TX: ${txId}`);
        if (typeof onSubmitted === "function") {
          onSubmitted();
        }
        watchSubmittedTx(txId, userAddress, actionLabel);
      },
      onCancel: () => {
        clearPendingTx(`${actionLabel} cancelada.`);
      },
    });
  } catch (error) {
    clearPendingTx(`No se pudo iniciar ${actionLabel}.`);
    console.error(`Error en ${actionLabel}:`, error);
  }
}

async function handleConnect() {
  try {
    await connect();
    updateUI();
    await refreshAllData();
  } catch (error) {
    console.error("Error al conectar:", error);
  }
}

async function mintToken(tokenId) {
  const tokenConfig = tokenContracts[tokenId];
  const userAddress = getUserAddress();

  if (!userAddress) {
    alert("Conecta tu wallet primero.");
    return;
  }

  await startContractAction({
    contractName: tokenConfig.contractName,
    functionName: "mint",
    functionArgs: [uintCV(MINT_AMOUNT), principalCV(userAddress)],
    actionLabel: `mintear ${tokenConfig.contractName}`,
  });
}

async function createPool() {
  const fee = parseUintInput(createPoolFeeInput, 500);

  if (fee <= 0) {
    alert("Ingresa un fee válido mayor a 0.");
    return;
  }

  let token0;
  let token1;

  try {
    [token0, token1] = normalizePoolTokens(
      parseContractPrincipal(createToken0Input?.value),
      parseContractPrincipal(createToken1Input?.value),
    );
  } catch (error) {
    alert(error.message);
    return;
  }

  if (token0.full === token1.full) {
    alert("Elige dos tokens distintos para crear la pool.");
    return;
  }

  const poolAlreadyExists = knownPools.some(
    (pool) =>
      pool.fee === fee &&
      pool.token0.full === token0.full &&
      pool.token1.full === token1.full,
  );

  if (poolAlreadyExists) {
    alert("Esa pool ya existe en el contrato desplegado.");
    return;
  }

  await startContractAction({
    contractName: ammContractName,
    functionName: "create-pool",
    functionArgs: [tokenToCV(token0), tokenToCV(token1), uintCV(fee)],
    actionLabel: `crear pool ${getPoolLabel({ token0, token1 })} fee ${fee}`,
  });
}

function getSelectedPoolConfig() {
  const rawValue = liquidityPoolSelect?.value;
  if (!rawValue) return null;

  try {
    const parsed = JSON.parse(decodeURIComponent(rawValue));
    return {
      token0: parseContractPrincipal(parsed.token0),
      token1: parseContractPrincipal(parsed.token1),
      fee: Number.parseInt(parsed.fee, 10),
    };
  } catch {
    return null;
  }
}

async function addLiquidity() {
  const userAddress = getUserAddress();
  const pool = getSelectedPoolConfig();
  const amount0Desired = parseUintInput(amount0DesiredInput, 0);
  const amount1Desired = parseUintInput(amount1DesiredInput, 0);
  const amount0Min = parseUintInput(amount0MinInput, 0);
  const amount1Min = parseUintInput(amount1MinInput, 0);

  if (!pool) {
    alert("Selecciona una pool existente para agregar liquidez.");
    return;
  }

  if (amount0Desired <= 0 || amount1Desired <= 0) {
    alert("Ingresa montos válidos para agregar liquidez.");
    return;
  }

  await startContractAction({
    contractName: ammContractName,
    functionName: "add-liquidity",
    functionArgs: [
      tokenToCV(pool.token0),
      tokenToCV(pool.token1),
      uintCV(pool.fee),
      uintCV(amount0Desired),
      uintCV(amount1Desired),
      uintCV(amount0Min),
      uintCV(amount1Min),
    ],
    postConditions: [
      buildTokenPostCondition(pool.token0, amount0Desired, userAddress),
      buildTokenPostCondition(pool.token1, amount1Desired, userAddress),
    ].filter(Boolean),
    actionLabel: `agregar liquidez a ${getPoolLabel(pool)} fee ${pool.fee}`,
  });
}

btnConnect.addEventListener("click", handleConnect);
btnLogout.addEventListener("click", () => {
  disconnect();
  updateUI();
  loadPools();
});
refreshBtn?.addEventListener("click", () => {
  setStatus("Actualizando datos on-chain...");
  refreshAllData();
});
createPoolBtn?.addEventListener("click", createPool);
addLiquidityBtn?.addEventListener("click", addLiquidity);

mintOneBtn?.addEventListener("click", () => mintToken("mock1"));
mintTwoBtn?.addEventListener("click", () => mintToken("mock2"));

window.refreshMockBalances = refreshMockBalances;
window.refreshAllData = refreshAllData;

updateUI();
renderMockBalances();
renderPoolSelect();
loadPools();
fetchRecentEvents();

if (isConnected()) {
  refreshAllData();
}
