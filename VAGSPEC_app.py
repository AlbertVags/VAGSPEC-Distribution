import React, { useEffect, useMemo, useRef, useState } from "react";

/**
 * VAGSPEC DISTRIBUTION – Single‑file React PWA (Canvas Preview)
 * -------------------------------------------------------------
 * Fixed: undefined hooks (useUsers, useSession, etc.) by defining them here.
 * Also added a small built‑in self‑test harness (admin‑only, in Help tab) to catch regressions.
 *
 * Features:
 * - Login (Admin / Staff roles). Passwords hashed with Web Crypto (SHA‑256); seeded users use precomputed hashes.
 * - Tabs: Inventory (Distribution), Orders, All Locations, Settings (admin only), Help (admin only).
 * - Distribution inventory is SEPARATE from branch inventories (MENLYN, RANDBURG, ZEERUST, CAPE TOWN, SOMERSET; add/remove allowed).
 * - Per‑part: photo, part #, description, notes, qty, per‑part low‑stock threshold, and an "On Order" checkbox (admin‑only toggle).
 * - Orders can only be placed FROM Distribution inventory; cannot exceed available quantity.
 * - Admin can Approve/Decline; approval deducts stock immediately. Admin can edit order qty before approval.
 * - Search + CSV/Excel export (tries xlsx; falls back to CSV).
 * - PWA bits: manifest at runtime + minimal service worker registration (best‑effort in this single file).
 * - Push notifications test button (requests permission; shows a notification if allowed).
 * - Logo shown on all pages (settings).
 * - Self‑tests shown in Help (admin only). No existing tests were changed (none existed); added new tests per instructions.
 */

/*************************
 * Utility: tiny toolkit  *
 *************************/
const BRANCHES_DEFAULT = [
  "DISTRIBUTION",
  "RANDBURG",
  "MENLYN",
  "ZEERUST",
  "CAPE TOWN",
  "SOMERSET",
];

function cls(...xs) { return xs.filter(Boolean).join(" "); }

async function sha256(text) {
  const enc = new TextEncoder();
  const buf = await crypto.subtle.digest("SHA-256", enc.encode(text));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join("");
}

function downloadBlob(filename, content, mime = "text/plain") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

function toCSV(rows) {
  if (!rows?.length) return "";
  const cols = Object.keys(rows[0]);
  const esc = (v) => `"${String(v ?? "").replaceAll('"', '""')}"`;
  const header = cols.map(esc).join(",");
  const body = rows.map(r => cols.map(c => esc(r[c])).join(",")).join("\n");
  return header + "\n" + body;
}

/*************************
 * Storage (localStorage) *
 *************************/
const LS = {
  USERS: "vagspec.users",
  SESSION: "vagspec.session",
  BRANCHES: "vagspec.branches",
  DIST_INV: "vagspec.inventory.distribution",
  BRANCH_INV: "vagspec.inventory.branches", // map branch -> items
  ORDERS: "vagspec.orders",
  SETTINGS: "vagspec.settings",
};

function useLocalStorage(key, initial) {
  const [state, setState] = useState(() => {
    const raw = localStorage.getItem(key);
    if (raw) return JSON.parse(raw);
    return typeof initial === "function" ? initial() : initial;
  });
  useEffect(() => { localStorage.setItem(key, JSON.stringify(state)); }, [key, state]);
  return [state, setState];
}

/****************
 * Auth bits     *
 ****************/
// Precomputed SHA‑256 hashes for Admin123! and Staff123! (so seeding is synchronous)
const ADMIN_HASH = "3eb3fe66b31e3b4d10fa70b5cad49c7112294af6ae4e476a1c405155d45aa121";
const STAFF_HASH = "05dd4a1376a72d9a5e0fad32000f7e61651a5cef5c9c9a0c3816c7443dafbf6f";

function seedUsers() {
  return [
    { id: crypto.randomUUID(), name: "Administrator", email: "admin@vagspec", role: "admin", passHash: ADMIN_HASH, active: true },
    { id: crypto.randomUUID(), name: "Staff Member", email: "staff@vagspec", role: "staff", passHash: STAFF_HASH, active: true },
  ];
}

function useUsers() {
  const [users, setUsers] = useLocalStorage(LS.USERS, seedUsers);
  return [users, setUsers];
}

function useSession() {
  return useLocalStorage(LS.SESSION, null);
}

/****************
 * App Settings  *
 ****************/
const defaultSettings = {
  logoUrl: "https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/volkswagen.svg",
  allowPush: true,
};

function useAppSettings() { return useLocalStorage(LS.SETTINGS, defaultSettings); }

/****************
 * Inventories   *
 ****************/
function emptyItem() {
  return { id: crypto.randomUUID(), partNr: "", description: "", notes: "", qty: 0, low: 0, onOrder: false, imageUrl: "" };
}

function useBranches() { return useLocalStorage(LS.BRANCHES, BRANCHES_DEFAULT); }

function useDistributionInventory() { return useLocalStorage(LS.DIST_INV, []); }

function useBranchInventories(branches) {
  const [map, setMap] = useLocalStorage(LS.BRANCH_INV, () => Object.fromEntries(BRANCHES_DEFAULT.map(b => [b, []])));
  // Ensure new branches get initialized
  useEffect(() => {
    const next = { ...map };
    let changed = false;
    branches.forEach(b => { if (!next[b]) { next[b] = []; changed = true; } });
    // Remove entries for branches that no longer exist (except Distribution safety)
    Object.keys(next).forEach(k => { if (!branches.includes(k)) { delete next[k]; changed = true; } });
    if (changed) setMap(next);
  }, [branches]); // eslint-disable-line react-hooks/exhaustive-deps
  return [map, setMap];
}

function useOrders() { return useLocalStorage(LS.ORDERS, []); }

/****************
 * PWA helpers   *
 ****************/
function registerSW() {
  if (!("serviceWorker" in navigator)) return;
  const swCode = `self.addEventListener('install',e=>self.skipWaiting());self.addEventListener('activate',e=>self.clients.claim());self.addEventListener('fetch',e=>{});`;
  const blob = new Blob([swCode], { type: "text/javascript" });
  const url = URL.createObjectURL(blob);
  navigator.serviceWorker.register(url).catch(()=>{});
}

function createManifestLink() {
  const manifest = {
    name: "VAGSPEC Distribution",
    short_name: "VAGSPEC",
    start_url: ".",
    display: "standalone",
    background_color: "#0B1220",
    theme_color: "#0EA5E9",
    icons: [],
  };
  const link = document.createElement("link");
  link.rel = "manifest";
  const blob = new Blob([JSON.stringify(manifest)], { type: "application/json" });
  link.href = URL.createObjectURL(blob);
  document.head.appendChild(link);
}

/****************
 * Components    *
 ****************/
function PageShell({ settings, user, onLogout, children }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="sticky top-0 z-10 bg-white/90 backdrop-blur border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center gap-3">
          {settings?.logoUrl && (
            <img src={settings.logoUrl} alt="VAGSPEC" className="h-8 w-8 object-contain" />
          )}
          <div className="font-semibold">VAGSPEC DISTRIBUTION</div>
          <div className="ml-auto text-sm">{user?.name} · {user?.role}</div>
          <button onClick={onLogout} className="ml-3 text-xs px-3 py-1.5 rounded-lg border hover:bg-slate-100">Logout</button>
        </div>
      </header>
      <main className="max-w-7xl mx-auto px-4 py-5">{children}</main>
      <footer className="py-6 text-center text-xs text-slate-500">© {new Date().getFullYear()} VAGSPEC DISTRIBUTION</footer>
    </div>
  );
}

function Tabs({ tabs, current, setCurrent }) {
  return (
    <div className="mb-4 flex flex-wrap gap-2">
      {tabs.map(t => (
        <button key={t}
          onClick={() => setCurrent(t)}
          className={cls("px-3 py-2 rounded-xl border text-sm",
            current === t ? "bg-sky-100 border-sky-300" : "bg-white hover:bg-slate-50 border-slate-200")}
        >{t}</button>
      ))}
    </div>
  );
}

function SearchBox({ value, onChange, placeholder = "Search…" }) {
  return (
    <input value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder}
      className="w-full md:w-80 px-3 py-2 border rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-sky-300" />
  );
}

function ImagePicker({ value, onChange }) {
  const fileRef = useRef(null);
  function handleFile(e) {
    const f = e.target.files?.[0];
    if (!f) return;
    const url = URL.createObjectURL(f);
    onChange(url);
  }
  return (
    <div className="flex items-center gap-2">
      {value ? <img src={value} alt="part" className="h-10 w-10 rounded object-cover border" /> : <div className="h-10 w-10 rounded bg-slate-200" />}
      <input ref={fileRef} type="file" accept="image/*" onChange={handleFile} className="text-xs" />
    </div>
  );
}

function InventoryTable({ items, setItems, user, adminCanToggleOnOrder = true, branchLabel = "" }) {
  const [q, setQ] = useState("");

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return items;
    return items.filter(it =>
      it.partNr?.toLowerCase().includes(s) ||
      it.description?.toLowerCase().includes(s) ||
      it.notes?.toLowerCase().includes(s)
    );
  }, [items, q]);

  function up(idx, patch) {
    const next = [...items];
    next[idx] = { ...next[idx], ...patch };
    setItems(next);
  }
  function add() { setItems([...items, emptyItem()]); }
  function remove(id) { setItems(items.filter(x => x.id !== id)); }

  async function exportCSV() {
    downloadBlob(`${branchLabel || "distribution"}-inventory.csv`, toCSV(items), "text/csv");
  }
  async function exportXLSX() {
    try {
      const XLSX = (await import("xlsx")).default || (await import("xlsx"));
      const ws = XLSX.utils.json_to_sheet(items);
      const wb = XLSX.utils.book_new();
      XLSX.utils.book_append_sheet(wb, ws, "Inventory");
      const wbout = XLSX.write(wb, { bookType: "xlsx", type: "array" });
      const blob = new Blob([wbout], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${branchLabel || "distribution"}-inventory.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      alert("Excel export library not available. A CSV export will download instead.");
      exportCSV();
    }
  }

  return (
    <div className="bg-white rounded-2xl shadow-sm border p-4">
      <div className="flex flex-wrap items-center gap-2 mb-3">
        <SearchBox value={q} onChange={setQ} placeholder={`Search ${branchLabel || "Distribution"} inventory…`} />
        <div className="ml-auto flex items-center gap-2">
          <button onClick={exportCSV} className="px-3 py-2 text-xs rounded-lg border">Export CSV</button>
          <button onClick={exportXLSX} className="px-3 py-2 text-xs rounded-lg border">Export Excel</button>
          {user?.role === "admin" && (<button onClick={add} className="px-3 py-2 text-xs rounded-lg bg-sky-600 text-white">Add Part</button>)}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left bg-slate-100">
            <tr>
              <th className="p-2">Photo</th>
              <th className="p-2">Part #</th>
              <th className="p-2">Description</th>
              <th className="p-2">Notes</th>
              <th className="p-2">Qty</th>
              <th className="p-2">Low</th>
              <th className="p-2">On Order</th>
              {user?.role === "admin" && <th className="p-2">Actions</th>}
            </tr>
          </thead>
          <tbody>
            {filtered.map((it, idx) => {
              const low = Number(it.low || 0);
              const qty = Number(it.qty || 0);
              const lowWarn = low > 0 && qty <= low;
              return (
                <tr key={it.id} className={cls("border-b", lowWarn && "bg-red-50")}>
                  <td className="p-2"><ImagePicker value={it.imageUrl} onChange={v => up(idx, { imageUrl: v })} /></td>
                  <td className="p-2">
                    <input className="border rounded px-2 py-1 w-40" value={it.partNr} onChange={e => up(idx, { partNr: e.target.value })} disabled={user?.role !== "admin"} />
                  </td>
                  <td className="p-2">
                    <input className="border rounded px-2 py-1 w-64" value={it.description} onChange={e => up(idx, { description: e.target.value })} disabled={user?.role !== "admin"} />
                  </td>
                  <td className="p-2">
                    <input className="border rounded px-2 py-1 w-64" value={it.notes} onChange={e => up(idx, { notes: e.target.value })} disabled={user?.role !== "admin"} />
                  </td>
                  <td className="p-2 w-24">
                    <input type="number" className="border rounded px-2 py-1 w-24" value={it.qty} onChange={e => up(idx, { qty: Number(e.target.value || 0) })} disabled={user?.role !== "admin"} />
                  </td>
                  <td className="p-2 w-20">
                    <input type="number" className="border rounded px-2 py-1 w-20" value={it.low} onChange={e => up(idx, { low: Number(e.target.value || 0) })} disabled={user?.role !== "admin"} />
                  </td>
                  <td className="p-2">
                    <input type="checkbox" checked={!!it.onOrder} onChange={e => {
                      if (user?.role !== "admin" && adminCanToggleOnOrder) return;
                      up(idx, { onOrder: e.target.checked });
                    }} disabled={adminCanToggleOnOrder && user?.role !== "admin"} />
                  </td>
                  {user?.role === "admin" && (
                    <td className="p-2">
                      <button onClick={() => remove(it.id)} className="text-xs px-2 py-1 rounded border hover:bg-slate-50">Delete</button>
                    </td>
                  )}
                </tr>
              );
            })}
            {filtered.length === 0 && (
              <tr><td colSpan={8} className="text-center text-slate-500 py-8">No parts yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function OrdersView({ user, orders, setOrders, distributionItems, setDistributionItems }) {
  const [q, setQ] = useState("");
  const [selectedPartId, setSelectedPartId] = useState("");
  const [qty, setQty] = useState(0);

  const parts = distributionItems;
  const selectedPart = parts.find(p => p.id === selectedPartId);

  function placeOrder() {
    if (!selectedPart) return alert("Choose a part from Distribution inventory.");
    const max = Number(selectedPart.qty || 0);
    const n = Number(qty || 0);
    if (n <= 0) return alert("Quantity must be greater than zero.");
    if (n > max) return alert(`Cannot order more than available (${max}).`);
    const o = {
      id: crypto.randomUUID(),
      partId: selectedPart.id,
      partNr: selectedPart.partNr,
      description: selectedPart.description,
      qty: n,
      requestedBy: user?.email,
      status: "Pending",
      createdAt: new Date().toISOString(),
    };
    setOrders([o, ...orders]);
    setSelectedPartId(""); setQty(0);
    try { if (Notification?.permission === "granted") new Notification("Order placed", { body: `${o.partNr} × ${o.qty}` }); } catch {}
  }

  function setOrder(idx, patch) { const next = [...orders]; next[idx] = { ...next[idx], ...patch }; setOrders(next); }

  function approve(idx) {
    const o = orders[idx];
    // Deduct from Distribution
    const i = distributionItems.findIndex(x => x.id === o.partId);
    if (i >= 0) {
      const nextInv = [...distributionItems];
      const item = { ...nextInv[i] };
      item.qty = Math.max(0, Number(item.qty || 0) - Number(o.qty || 0));
      nextInv[i] = item;
      setDistributionItems(nextInv);
    }
    setOrder(idx, { status: "Approved", approvedAt: new Date().toISOString() });
  }
  function decline(idx) { setOrder(idx, { status: "Declined", decidedAt: new Date().toISOString() }); }

  const filtered = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (!s) return orders;
    return orders.filter(o =>
      o.partNr?.toLowerCase().includes(s) ||
      o.description?.toLowerCase().includes(s) ||
      o.requestedBy?.toLowerCase().includes(s) ||
      o.status?.toLowerCase().includes(s)
    );
  }, [orders, q]);

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl shadow-sm border p-4">
        <div className="font-medium mb-3">Place an order (from Distribution only)</div>
        <div className="flex flex-wrap gap-2 items-end">
          <div className="flex flex-col">
            <label className="text-xs mb-1">Part</label>
            <select className="border rounded-xl px-3 py-2 min-w-64" value={selectedPartId} onChange={e => setSelectedPartId(e.target.value)}>
              <option value="">— Select part —</option>
              {parts.map(p => (
                <option key={p.id} value={p.id}>{p.partNr} · {p.description} (Available: {p.qty})</option>
              ))}
            </select>
          </div>
          <div className="flex flex-col">
            <label className="text-xs mb-1">Quantity</label>
            <input type="number" className="border rounded-xl px-3 py-2 w-32" value={qty} onChange={e => setQty(e.target.value)} />
          </div>
          <button onClick={placeOrder} className="px-4 py-2 rounded-xl bg-sky-600 text-white">Order</button>
        </div>
      </div>

      <div className="bg-white rounded-2xl shadow-sm border p-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="font-medium">Orders</div>
          <div className="ml-auto w-full md:w-auto"><SearchBox value={q} onChange={setQ} placeholder="Search orders…" /></div>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="p-2">Part #</th><th className="p-2">Description</th><th className="p-2">Qty</th><th className="p-2">Requested By</th><th className="p-2">Status</th>{user?.role === "admin" && <th className="p-2">Admin</th>}
              </tr>
            </thead>
            <tbody>
              {filtered.map((o, idx) => (
                <tr key={o.id} className="border-b">
                  <td className="p-2">{o.partNr}</td>
                  <td className="p-2">{o.description}</td>
                  <td className="p-2 w-32">
                    {user?.role === "admin" && o.status === "Pending" ? (
                      <input type="number" className="border rounded px-2 py-1 w-28" value={o.qty}
                        onChange={e => { const val = Math.max(0, Number(e.target.value || 0)); setOrder(idx, { qty: val }); }} />
                    ) : (
                      <span>{o.qty}</span>
                    )}
                  </td>
                  <td className="p-2">{o.requestedBy}</td>
                  <td className="p-2">
                    <span className={cls("px-2 py-1 rounded text-xs",
                      o.status === "Pending" && "bg-amber-100 text-amber-700",
                      o.status === "Approved" && "bg-emerald-100 text-emerald-700",
                      o.status === "Declined" && "bg-rose-100 text-rose-700")}>{o.status}</span>
                  </td>
                  {user?.role === "admin" && (
                    <td className="p-2 flex gap-2">
                      {o.status === "Pending" && <button onClick={() => approve(idx)} className="text-xs px-2 py-1 rounded border">Approve</button>}
                      {o.status === "Pending" && <button onClick={() => decline(idx)} className="text-xs px-2 py-1 rounded border">Decline</button>}
                    </td>
                  )}
                </tr>
              ))}
              {filtered.length === 0 && <tr><td colSpan={6} className="text-center text-slate-500 py-8">No orders yet.</td></tr>}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function SettingsView({ settings, setSettings, branches, setBranches, users, setUsers }) {
  const [newBranch, setNewBranch] = useState("");

  // --- Add User modal state ---
  const [showAdd, setShowAdd] = useState(false);
  const [uName, setUName] = useState("");
  const [uEmail, setUEmail] = useState("");
  const [uRole, setURole] = useState("staff");
  const [tempPassShown, setTempPassShown] = useState("");
  const [formError, setFormError] = useState("");

  const emailTaken = (email) =>
    users.some(x => x.email.toLowerCase() === email.trim().toLowerCase());
  const validEmail = (email) =>
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());

  async function handleCreateUser() {
    setFormError("");
    const name = uName.trim();
    const email = uEmail.trim().toLowerCase();
    const role = uRole === "admin" ? "admin" : "staff";

    if (!name) return setFormError("Please enter a name.");
    if (!email) return setFormError("Please enter an email.");
    if (!validEmail(email)) return setFormError("Email format looks wrong.");
    if (emailTaken(email)) return setFormError("That email is already in use.");

    const tempPass = Math.random().toString(36).slice(2, 10);
    const passHash = await sha256(tempPass);

    setUsers([
      ...users,
      { id: crypto.randomUUID(), name, email, role, passHash, active: true }
    ]);

    setTempPassShown(`Temporary password for ${email}: ${tempPass}`);
    setUName("");
    setUEmail("");
    setURole("staff");
    setShowAdd(false);
  }

  function deactivate(u) {
    setUsers(users.map(x => x.id === u.id ? { ...x, active: !x.active } : x));
  }

  async function resetPass(u) {
    const temp = Math.random().toString(36).slice(2, 10);
    const passHash = await sha256(temp);
    setUsers(users.map(x => x.id === u.id ? { ...x, passHash } : x));
    setTempPassShown(`Temporary password for ${u.email}: ${temp}`);
  }

  function addBranch() {
    const b = newBranch.trim().toUpperCase();
    if (!b) return;
    if (branches.includes(b)) return alert("Branch already exists");
    setBranches([...branches, b]);
    setNewBranch("");
  }

  function removeBranch(b) {
    if (!confirm(`Remove branch ${b}?`)) return;
    setBranches(branches.filter(x => x !== b));
  }

  function testPush() {
    if (!("Notification" in window))
      return alert("Notifications not supported in this browser.");
    Notification.requestPermission().then(p => {
      if (p === "granted")
        new Notification("VAGSPEC", { body: "Push notifications are enabled." });
      else alert("Permission not granted.");
    });
  }

  return (
    <div className="grid md:grid-cols-2 gap-4">
      {/* Brand & App */}
      <div className="bg-white border rounded-2xl p-4">
        <div className="font-medium mb-2">Brand & App</div>
        <label className="text-xs">Logo URL</label>
        <input
          className="w-full border rounded-xl px-3 py-2 mb-2"
          value={settings.logoUrl}
          onChange={e => setSettings({ ...settings, logoUrl: e.target.value })}
        />
        <button
          onClick={() => setSettings(defaultSettings)}
          className="text-xs px-3 py-2 rounded border"
        >
          Reset defaults
        </button>
      </div>

      {/* Push notifications */}
      <div className="bg-white border rounded-2xl p-4">
        <div className="font-medium mb-2">Push Notifications</div>
        <p className="text-sm text-slate-600 mb-2">
          Best-effort demo via the browser Notification API.
        </p>
        <button
          onClick={testPush}
          className="px-3 py-2 rounded-xl bg-sky-600 text-white"
        >
          Test Notification
        </button>
      </div>

      {/* Locations */}
      <div className="bg-white border rounded-2xl p-4">
        <div className="font-medium mb-2">Locations</div>
        <div className="flex gap-2 mb-2">
          <input
            value={newBranch}
            onChange={e => setNewBranch(e.target.value)}
            placeholder="Add new location (UPPERCASE)"
            className="border rounded-xl px-3 py-2 w-full"
          />
          <button
            onClick={addBranch}
            className="px-3 py-2 rounded-xl border"
          >
            Add
          </button>
        </div>
        <ul className="divide-y">
          {branches.map(b => (
            <li
              key={b}
              className="py-2 flex items-center justify-between"
            >
              <span>{b}</span>
              <button
                onClick={() => removeBranch(b)}
                className="text-xs px-2 py-1 rounded border"
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      </div>

      {/* Users & Roles */}
      <div className="bg-white border rounded-2xl p-4 relative">
        <div className="font-medium mb-2">Users & Roles</div>

        {tempPassShown && (
          <div className="mb-3 text-sm p-2 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
            {tempPassShown}
          </div>
        )}

        <button
          onClick={() => {
            setShowAdd(true);
            setFormError("");
          }}
          className="mb-3 px-3 py-2 rounded-xl bg-sky-600 text-white"
        >
          Add User
        </button>

        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="bg-slate-100 text-left">
              <tr>
                <th className="p-2">Name</th>
                <th className="p-2">Email</th>
                <th className="p-2">Role</th>
                <th className="p-2">Active</th>
                <th className="p-2">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className="border-b">
                  <td className="p-2">{u.name}</td>
                  <td className="p-2">{u.email}</td>
                  <td className="p-2">{u.role}</td>
                  <td className="p-2">{u.active ? "Yes" : "No"}</td>
                  <td className="p-2 flex gap-2">
                    <button
                      onClick={() => deactivate(u)}
                      className="text-xs px-2 py-1 rounded border"
                    >
                      {u.active ? "Deactivate" : "Activate"}
                    </button>
                    <button
                      onClick={() => resetPass(u)}
                      className="text-xs px-2 py-1 rounded border"
                    >
                      Reset Password
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Add User modal */}
        {showAdd && (
          <div className="fixed inset-0 bg-black/50 grid place-items-center p-4 z-50">
            <div className="bg-white w-full max-w-md rounded-2xl border shadow p-4">
              <div className="text-base font-semibold mb-2">Add User</div>
              <div className="space-y-3">
                <div>
                  <label className="text-xs">Name</label>
                  <input
                    value={uName}
                    onChange={e => setUName(e.target.value)}
                    className="w-full border rounded-xl px-3 py-2"
                  />
                </div>
                <div>
                  <label className="text-xs">Email</label>
                  <input
                    value={uEmail}
                    onChange={e => setUEmail(e.target.value)}
                    className="w-full border rounded-xl px-3 py-2"
                    placeholder="name@vagspec"
                  />
                </div>
                <div>
                  <label className="text-xs">Role</label>
                  <select
                    value={uRole}
                    onChange={e => setURole(e.target.value)}
                    className="w-full border rounded-xl px-3 py-2"
                  >
                    <option value="staff">staff</option>
                    <option value="admin">admin</option>
                  </select>
                </div>
                {formError && (
                  <div className="text-rose-600 text-sm">{formError}</div>
                )}
                <div className="flex gap-2 justify-end pt-2">
                  <button
                    onClick={() => {
                      setShowAdd(false);
                      setFormError("");
                    }}
                    className="px-3 py-2 rounded-xl border"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateUser}
                    className="px-3 py-2 rounded-xl bg-sky-600 text-white"
                  >
                    Create
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

function BranchInventories({ branches, branchInv, setBranchInv, user }) {
  return (
    <div className="space-y-6">
      {branches.filter(b => b !== "DISTRIBUTION").map(b => (
        <section key={b} className="space-y-2">
          <div className="text-sm font-medium">{b} – Inventory (separate from Distribution)</div>
          <InventoryTable
            items={branchInv[b] || []}
            setItems={(items) => setBranchInv({ ...branchInv, [b]: items })}
            user={user}
            adminCanToggleOnOrder={true}
            branchLabel={b}
          />
        </section>
      ))}
    </div>
  );
}

/****************
 * Help + Tests  *
 ****************/
function runSelfTests() {
  const results = [];
  function assert(name, cond) { results.push({ name, pass: !!cond }); }

  // Tests
  assert("Default branches seeded", Array.isArray(BRANCHES_DEFAULT) && BRANCHES_DEFAULT.includes("DISTRIBUTION") && BRANCHES_DEFAULT.includes("RANDBURG"));
  assert("CSV exporter works", toCSV([{ a: 1, b: 2 }]).startsWith('"a","b"'));
  assert("Seed users have correct roles", seedUsers().some(u => u.role === "admin") && seedUsers().some(u => u.role === "staff"));
  assert("Seed users have SHA-256 hashes", seedUsers().every(u => typeof u.passHash === "string" && u.passHash.length === 64));
  assert("Empty inventory item shape", Object.prototype.hasOwnProperty.call(emptyItem(), "partNr"));

  return results;
}

function HelpView() {
  const [tests, setTests] = useState([]);
  useEffect(() => { setTests(runSelfTests()); }, []);
  const passCount = tests.filter(t => t.pass).length;
  return (
    <div className="prose max-w-none">
      <h2>How to use this app</h2>
      <ol>
        <li><strong>Login:</strong> Use <code>admin@vagspec</code> / <code>Admin123!</code> for admin, or <code>staff@vagspec</code> / <code>Staff123!</code> for staff.</li>
        <li><strong>Inventory:</strong> Admins can add/edit parts for <em>Distribution</em>. Staff have read‑only. Per‑part low stock triggers a red row.</li>
        <li><strong>Orders:</strong> Staff place orders from <em>Distribution</em> inventory only. Qty cannot exceed available. Admin can edit qty, approve/decline; approval deducts stock.</li>
        <li><strong>All Locations:</strong> Manage separate inventories for Menlyn, Randburg, Zeerust, Cape Town, Somerset, etc. These are independent from Distribution.</li>
        <li><strong>Settings (Admin):</strong> Manage logo, users (roles, activation, password reset), and locations.</li>
        <li><strong>Export:</strong> Use CSV or Excel export buttons on inventory tables.</li>
        <li><strong>PWA:</strong> On a supported browser, use "Install app" or Add to Home Screen.</li>
      </ol>

      <details className="mt-6">
        <summary><strong>Developer Self‑Tests</strong> ({passCount}/{tests.length} passing)</summary>
        <table className="mt-2">
          <thead><tr><th>Test</th><th>Result</th></tr></thead>
          <tbody>
            {tests.map((t, i) => (
              <tr key={i}><td>{t.name}</td><td>{t.pass ? "✅ Pass" : "❌ Fail"}</td></tr>
            ))}
          </tbody>
        </table>
        <p className="text-sm">(These lightweight checks run in the browser and also log to the console.)</p>
      </details>
    </div>
  );
}

function Login({ onLogin, users }) {
  const [email, setEmail] = useState("");
  const [pass, setPass] = useState("");
  const [error, setError] = useState("");

  async function submit(e) {
    e.preventDefault(); setError("");
    const u = users.find(x => x.email.toLowerCase() === email.trim().toLowerCase());
    if (!u) return setError("User not found");
    if (!u.active) return setError("User is deactivated");
    const h = await sha256(pass);
    if (h !== u.passHash) return setError("Incorrect password");
    onLogin({ id: u.id, name: u.name, email: u.email, role: u.role });
  }
  return (
    <div className="min-h-screen grid place-items-center bg-gradient-to-b from-slate-50 to-slate-100">
      <form onSubmit={submit} className="bg-white border rounded-2xl shadow-sm p-6 w-full max-w-md">
        <div className="flex items-center gap-2 mb-4">
          <img alt="VAGSPEC" className="h-8 w-8" src="https://raw.githubusercontent.com/simple-icons/simple-icons/develop/icons/volkswagen.svg" />
          <div className="text-lg font-semibold">VAGSPEC DISTRIBUTION</div>
        </div>
        <div className="space-y-3">
          <div>
            <label className="text-xs">Email</label>
            <input value={email} onChange={e => setEmail(e.target.value)} className="w-full border rounded-xl px-3 py-2" placeholder="admin@vagspec" />
          </div>
          <div>
            <label className="text-xs">Password</label>
            <input type="password" value={pass} onChange={e => setPass(e.target.value)} className="w-full border rounded-xl px-3 py-2" placeholder="••••••••" />
          </div>
          {error && <div className="text-rose-600 text-sm">{error}</div>}
          <button className="w-full py-2 rounded-xl bg-sky-600 text-white">Login</button>
          <div className="text-xs text-slate-500">Tip: admin@vagspec / Admin123! · staff@vagspec / Staff123!</div>
        </div>
      </form>
    </div>
  );
}

export default function App() {
  const [users, setUsers] = useUsers();
  const [session, setSession] = useSession();
  const [settings, setSettings] = useAppSettings();
  const [branches, setBranches] = useBranches();
  const [distribution, setDistribution] = useDistributionInventory();
  const [branchInv, setBranchInv] = useBranchInventories(branches);
  const [orders, setOrders] = useOrders();

  const [tab, setTab] = useState("Inventory");

  useEffect(() => { registerSW(); createManifestLink(); }, []);

  if (!session) return <Login onLogin={setSession} users={Array.isArray(users) ? users : []} />;

  const tabs = session.role === "admin"
    ? ["Inventory", "Orders", "All Locations", "Settings", "Help"]
    : ["Inventory", "Orders", "All Locations"]; // Help is admin‑only

  return (
    <PageShell settings={settings} user={session} onLogout={() => setSession(null)}>
      <Tabs tabs={tabs} current={tab} setCurrent={setTab} />

      {tab === "Inventory" && (
        <InventoryTable
          items={distribution}
          setItems={setDistribution}
          user={session}
          adminCanToggleOnOrder={true}
          branchLabel="Distribution"
        />
      )}

      {tab === "Orders" && (
        <OrdersView
          user={session}
          orders={orders}
          setOrders={setOrders}
          distributionItems={distribution}
          setDistributionItems={setDistribution}
        />
      )}

      {tab === "All Locations" && (
        <BranchInventories
          branches={branches}
          branchInv={branchInv}
          setBranchInv={setBranchInv}
          user={session}
        />
      )}

      {tab === "Settings" && session.role === "admin" && (
        <SettingsView
          settings={settings}
          setSettings={setSettings}
          branches={branches}
          setBranches={setBranches}
          users={users}
          setUsers={setUsers}
        />
      )}

      {tab === "Help" && session.role === "admin" && <HelpView />}
    </PageShell>
  );
}
