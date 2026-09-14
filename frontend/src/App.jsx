import React, { useEffect, useMemo, useState } from "react";
import {
  Activity,
  ArrowDownRight,
  ArrowUpRight,
  BrainCircuit,
  CheckCircle2,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  Gauge,
  LayoutDashboard,
  Menu,
  Sparkles,
  Package,
  RefreshCw,
  Search,
  ShieldCheck,
  Star,
  Target,
  Truck,
  UserRound,
  Users,
  X,
  Zap,
  AlertTriangle,
} from "lucide-react";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

const API_BASE =
  process.env.REACT_APP_API_URL || "http://localhost:8000";

async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(
      body.detail || `Request failed (${res.status})`
    );
  }

  return body;
}

const money = (n) =>
  `R$${Number(n || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const pct = (n) => `${Number(n || 0).toFixed(1)}%`;

function ShellIcon({ icon: Icon, active }) {
  return (
    <span className={`nav-icon ${active ? "active" : ""}`}>
      <Icon
        size={18}
        strokeWidth={active ? 2.4 : 2}
      />
    </span>
  );
}

function Card({
  children,
  className = "",
  title,
  action,
}) {
  return (
    <section className={`card ${className}`}>
      {(title || action) && (
        <div className="card-head">
          {title && <h3>{title}</h3>}
          {action}
        </div>
      )}

      {children}
    </section>
  );
}

function Kpi({
  icon: Icon,
  label,
  value,
  note,
  tone = "blue",
}) {
  return (
    <div className="kpi-card">
      <div className={`kpi-icon ${tone}`}>
        <Icon size={20} />
      </div>

      <div className="kpi-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        {note && <small>{note}</small>}
      </div>
    </div>
  );
}

function Empty({ label }) {
  return (
    <div className="empty">
      <CircleHelp size={18} />
      {label}
    </div>
  );
}

function Loading({
  label = "Loading live data...",
}) {
  return (
    <div className="loading">
      <RefreshCw
        size={17}
        className="spin"
      />
      {label}
    </div>
  );
}

/* =========================================================
   OVERVIEW
========================================================= */

function Overview({ go }) {
  const [data, setData] = useState(null);
  const [trend, setTrend] = useState([]);
  const [customers, setCustomers] = useState(null);
  const [delivery, setDelivery] = useState(null);
  const [sat, setSat] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    Promise.all([
      api("/api/analytics/overview"),
      api("/api/analytics/revenue-trend"),
      api("/api/analytics/customers"),
      api("/api/analytics/delivery"),
      api("/api/analytics/satisfaction"),
    ])
      .then(
        ([
          overview,
          revenue,
          customerData,
          deliveryData,
          satisfaction,
        ]) => {
          setData(overview);
          setTrend(revenue.trend || []);
          setCustomers(customerData);
          setDelivery(deliveryData);
          setSat(satisfaction);
        }
      )
      .catch((e) => {
        setError(e.message);
      });
  }, []);

  if (error) {
    return (
      <Card>
        <div className="error">
          <AlertTriangle size={18} />
          {error}
        </div>
      </Card>
    );
  }

  if (!data) {
    return (
      <Loading label="Building your business overview..." />
    );
  }

  const last =
    trend.length > 0
      ? trend[trend.length - 1]?.revenue || 0
      : 0;

  const prev =
    trend.length > 1
      ? trend[trend.length - 2]?.revenue || 0
      : 0;

  const change = prev
    ? ((last - prev) / prev) * 100
    : 0;

  const dist = sat?.score_distribution
    ? Object.entries(sat.score_distribution).map(
        ([score, n]) => ({
          score,
          n,
        })
      )
    : [];

  return (
    <div className="page">
      <div className="hero">
        <div>
          <div className="eyebrow">
            <span className="live-dot" />
            LIVE BUSINESS INTELLIGENCE
          </div>

          <h1>
            Know your customers.
            <br />
            <em>Grow with confidence.</em>
          </h1>

          <p>
            A decision-ready view of revenue, customers,
            delivery and customer experience — powered by
            your live data.
          </p>
        </div>

        <button
          className="hero-button"
          onClick={() => go("ai")}
        >
          <Sparkles size={17} />
          Ask your data
          <ChevronRight size={16} />
        </button>
      </div>

      <div className="kpi-grid">
        <Kpi
          icon={Activity}
          label="Revenue"
          value={money(data.total_revenue)}
          note="Delivered orders"
          tone="blue"
        />

        <Kpi
          icon={Package}
          label="Delivered orders"
          value={data.delivered_orders.toLocaleString()}
          note={`AOV ${money(data.average_order_value)}`}
          tone="violet"
        />

        <Kpi
          icon={Users}
          label="Customers analyzed"
          value={data.unique_customers.toLocaleString()}
          note="Segmented customers"
          tone="mint"
        />

        <Kpi
          icon={Star}
          label="Customer satisfaction"
          value={
            sat
              ? Number(sat.average_review_score).toFixed(2)
              : "—"
          }
          note={
            sat
              ? `${sat.total_reviews.toLocaleString()} reviews`
              : ""
          }
          tone="amber"
        />
      </div>

      <div className="grid-2">
        <Card
          title="Revenue momentum"
          action={
            <span
              className={`trend-pill ${
                change < 0 ? "down" : ""
              }`}
            >
              {change >= 0 ? (
                <ArrowUpRight size={14} />
              ) : (
                <ArrowDownRight size={14} />
              )}
              {Math.abs(change).toFixed(1)}% vs previous month
            </span>
          }
        >
          <div className="chart-wrap tall">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <AreaChart data={trend}>
                <defs>
                  <linearGradient
                    id="revenueFill"
                    x1="0"
                    y1="0"
                    x2="0"
                    y2="1"
                  >
                    <stop
                      offset="0%"
                      stopColor="#5b5ff1"
                      stopOpacity=".28"
                    />
                    <stop
                      offset="100%"
                      stopColor="#5b5ff1"
                      stopOpacity="0"
                    />
                  </linearGradient>
                </defs>

                <CartesianGrid
                  stroke="#edf0f5"
                  vertical={false}
                />

                <XAxis
                  dataKey="month"
                  tick={{
                    fontSize: 11,
                    fill: "#8991a5",
                  }}
                  axisLine={false}
                  tickLine={false}
                />

                <YAxis
                  tick={{
                    fontSize: 11,
                    fill: "#8991a5",
                  }}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) =>
                    `R$${Math.round(v / 1000)}k`
                  }
                />

                <Tooltip
                  formatter={(v) => [
                    money(v),
                    "Revenue",
                  ]}
                  contentStyle={{
                    border: "0",
                    borderRadius: 14,
                    boxShadow:
                      "0 10px 30px #27314a18",
                  }}
                />

                <Area
                  type="monotone"
                  dataKey="revenue"
                  stroke="#5b5ff1"
                  strokeWidth={3}
                  fill="url(#revenueFill)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card
          title="What deserves attention?"
          action={
            <button
              className="link-btn"
              onClick={() => go("operations")}
            >
              View operations
              <ChevronRight size={14} />
            </button>
          }
        >
          <div className="insight-list">
            <div className="insight critical">
              <div className="insight-symbol">
                <Truck size={17} />
              </div>

              <div>
                <b>Delivery performance</b>
                <span>
                  {delivery
                    ? `${pct(
                        delivery.late_delivery_rate_pct
                      )} of delivered orders arrived late.`
                    : "Analysing..."}
                </span>
              </div>

              <ChevronRight size={16} />
            </div>

            <div className="insight">
              <div className="insight-symbol">
                <Users size={17} />
              </div>

              <div>
                <b>Repeat customers</b>
                <span>
                  {customers
                    ? `${pct(
                        customers.repeat_rate_pct
                      )} of customers have purchased more than once.`
                    : "Analysing..."}
                </span>
              </div>

              <ChevronRight size={16} />
            </div>

            <div className="insight">
              <div className="insight-symbol">
                <Star size={17} />
              </div>

              <div>
                <b>Customer voice</b>
                <span>
                  {sat
                    ? `Average review score is ${Number(
                        sat.average_review_score
                      ).toFixed(2)} out of 5.`
                    : "Analysing..."}
                </span>
              </div>

              <ChevronRight size={16} />
            </div>
          </div>

          <div className="mini-callout">
            <Sparkles size={16} />

            <span>
              <b>AI can explain the numbers.</b>{" "}
              Ask a business question and get an
              evidence-based answer.
            </span>

            <button onClick={() => go("ai")}>
              Try it
            </button>
          </div>
        </Card>
      </div>

      <div className="grid-3">
        <Card title="Customer mix">
          <div className="donut-row">
            <div className="donut">
              <ResponsiveContainer
                width="100%"
                height="100%"
              >
                <PieChart>
                  <Pie
                    data={[
                      {
                        name: "Repeat",
                        value:
                          customers?.repeat_customers || 0,
                      },
                      {
                        name: "One-time",
                        value: Math.max(
                          (customers?.total_customers || 0) -
                            (customers?.repeat_customers || 0),
                          0
                        ),
                      },
                    ]}
                    innerRadius={43}
                    outerRadius={61}
                    dataKey="value"
                    strokeWidth={0}
                  >
                    <Cell fill="#5b5ff1" />
                    <Cell fill="#e8eaf2" />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>

              <div>
                <b>
                  {customers
                    ? pct(customers.repeat_rate_pct)
                    : "—"}
                </b>
                <span>repeat</span>
              </div>
            </div>

            <div className="legend">
              <span>
                <i className="dot purple" />
                Repeat{" "}
                <b>
                  {customers?.repeat_customers?.toLocaleString() ||
                    "—"}
                </b>
              </span>

              <span>
                <i className="dot gray" />
                One-time{" "}
                <b>
                  {customers
                    ? (
                        customers.total_customers -
                        customers.repeat_customers
                      ).toLocaleString()
                    : "—"}
                </b>
              </span>
            </div>
          </div>
        </Card>

        <Card title="Delivery health">
          <div className="metric-big">
            {delivery
              ? Number(
                  delivery.average_delivery_days
                ).toFixed(1)
              : "—"}{" "}
            <small>days</small>
          </div>

          <div className="progress">
            <span
              style={{
                width: `${Math.min(
                  Number(
                    delivery?.late_delivery_rate_pct || 0
                  ),
                  100
                )}%`,
              }}
            />
          </div>

          <div className="muted-row">
            <span>Late deliveries</span>
            <b>
              {delivery
                ? pct(
                    delivery.late_delivery_rate_pct
                  )
                : "—"}
            </b>
          </div>
        </Card>

        <Card title="Review distribution">
          <div className="chart-wrap small">
            <ResponsiveContainer
              width="100%"
              height="100%"
            >
              <BarChart data={dist}>
                <XAxis
                  dataKey="score"
                  tick={{
                    fontSize: 11,
                    fill: "#8991a5",
                  }}
                  axisLine={false}
                  tickLine={false}
                />

                <YAxis hide />

                <Tooltip
                  contentStyle={{
                    border: 0,
                    borderRadius: 12,
                  }}
                />

                <Bar
                  dataKey="n"
                  radius={[5, 5, 2, 2]}
                  fill="#f5b94c"
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}

/* =========================================================
   CUSTOMERS
========================================================= */

function Customers({ openCustomer }) {
  const [data, setData] = useState(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    api("/api/analytics/customers")
      .then(setData)
      .catch(() => {});
  }, []);

  if (!data) {
    return (
      <Loading label="Loading customer intelligence..." />
    );
  }

  const filtered = (data.top_states || []).filter(
    (x) =>
      x.state
        .toLowerCase()
        .includes(query.toLowerCase())
  );

  return (
    <div className="page">
      <PageTitle
        eyebrow="CUSTOMER INTELLIGENCE"
        title="See who drives your business"
        sub="Turn customer behaviour into clear, actionable segments."
      />

      <div className="kpi-grid three">
        <Kpi
          icon={Users}
          label="Total customers"
          value={data.total_customers.toLocaleString()}
          note="Unique identities"
          tone="blue"
        />

        <Kpi
          icon={RefreshCw}
          label="Repeat customers"
          value={data.repeat_customers.toLocaleString()}
          note={`${pct(data.repeat_rate_pct)} repeat rate`}
          tone="mint"
        />

        <Kpi
          icon={Target}
          label="Opportunity"
          value={`${(
            100 - Number(data.repeat_rate_pct || 0)
          ).toFixed(1)}%`}
          note="One-time customer share"
          tone="violet"
        />
      </div>

      <div className="grid-2">
        <Card title="Customer geography">
          <div className="table-head">
            <span>State</span>
            <span>Customers</span>
          </div>

          {filtered.map((x, i) => (
            <div
              className="table-row"
              key={x.state}
            >
              <span>
                <i className="rank">{i + 1}</i>
                {x.state}
              </span>

              <b>
                {x.customers.toLocaleString()}
              </b>
            </div>
          ))}
        </Card>

        <Card
          title="Customer intelligence"
          className="feature-card"
        >
          <div className="feature-icon">
            <BrainCircuit size={24} />
          </div>

          <h3>
            Want to understand one customer?
          </h3>

          <p>
            Search a real customer and see their
            purchase history, value, predicted
            behaviour and personalised recommendations.
          </p>

          <button
            className="primary"
            onClick={openCustomer}
          >
            <Search size={16} />
            Open Customer 360
          </button>
        </Card>
      </div>

      <Card title="How the intelligence works">
        <div className="journey">
          <div>
            <span className="step">01</span>
            <b>Observe</b>
            <small>Purchase behaviour</small>
          </div>

          <ChevronRight />

          <div>
            <span className="step">02</span>
            <b>Understand</b>
            <small>RFM + ML patterns</small>
          </div>

          <ChevronRight />

          <div>
            <span className="step">03</span>
            <b>Predict</b>
            <small>Retention + value</small>
          </div>

          <ChevronRight />

          <div>
            <span className="step">04</span>
            <b>Act</b>
            <small>Recommendations</small>
          </div>
        </div>
      </Card>
    </div>
  );
}

/* =========================================================
   CUSTOMER 360
========================================================= */

function Customer360() {
  const [id, setId] = useState("");
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const search = async () => {
    if (!id.trim()) return;

    setLoading(true);
    setError("");

    try {
      const result = await api(
        `/api/customers/${encodeURIComponent(
          id.trim()
        )}`
      );

      setProfile(result);
    } catch (e) {
      setError(e.message);
      setProfile(null);
    } finally {
      setLoading(false);
    }
  };

  const segment =
    profile?.segment?.segment_cluster != null
      ? `Customer segment ${profile.segment.segment_cluster}`
      : profile?.segment?.status ||
        "Not available";

  return (
    <div className="page">
      <PageTitle
        eyebrow="CUSTOMER 360"
        title="One customer. One clear story."
        sub="Explore a real customer across purchases, value, risk and recommendations."
      />

      <div className="search-hero">
        <Search size={19} />

        <input
          value={id}
          onChange={(e) => setId(e.target.value)}
          onKeyDown={(e) =>
            e.key === "Enter" && search()
          }
          placeholder="Paste a customer ID to explore..."
        />

        <button
          className="primary"
          onClick={search}
        >
          Explore customer
        </button>
      </div>

      {loading && (
        <Loading label="Building customer profile..." />
      )}

      {error && (
        <div className="error">
          <AlertTriangle size={18} />
          {error}
        </div>
      )}

      {profile && (
        <div className="customer-view">
          <div className="profile-banner">
            <div className="avatar">
              <UserRound size={28} />
            </div>

            <div>
              <span className="eyebrow">
                CUSTOMER PROFILE
              </span>

              <h2>
                {profile.city || "Customer"}{" "}
                <span>
                  · {profile.state || "—"}
                </span>
              </h2>

              <small className="mono">
                {profile.customer_unique_id}
              </small>
            </div>

            <div className="segment-chip">
              <Sparkles size={14} />
              {segment}
            </div>
          </div>

          <div className="kpi-grid three">
            <Kpi
              icon={Package}
              label="Delivered orders"
              value={profile.order_count}
              note={`Since ${
                profile.first_purchase_date || "—"
              }`}
              tone="blue"
            />

            <Kpi
              icon={Activity}
              label="Customer value"
              value={money(profile.total_revenue)}
              note={`AOV ${money(
                profile.average_order_value
              )}`}
              tone="mint"
            />

            <Kpi
              icon={Target}
              label="Return likelihood"
              value={
                profile.retention_prediction
                  ?.probability != null
                  ? pct(
                      profile.retention_prediction
                        .probability * 100
                    )
                  : "—"
              }
              note="Model prediction"
              tone="violet"
            />
          </div>

          <div className="grid-2">
            <Card title="What we know">
              <div className="facts">
                <span>
                  <b>Location</b>
                  {profile.city || "—"},{" "}
                  {profile.state || "—"}
                </span>

                <span>
                  <b>First purchase</b>
                  {profile.first_purchase_date ||
                    "—"}
                </span>

                <span>
                  <b>Last purchase</b>
                  {profile.last_purchase_date ||
                    "—"}
                </span>

                <span>
                  <b>Recency</b>
                  {profile.rfm?.recency_days != null
                    ? `${profile.rfm.recency_days} days`
                    : "—"}
                </span>
              </div>
            </Card>

            <Card title="Predicted next order">
              <div className="prediction">
                <div>
                  <span>
                    Expected order value
                  </span>

                  <strong>
                    {profile
                      .predicted_next_order_value
                      ?.predicted_value != null
                      ? money(
                          profile
                            .predicted_next_order_value
                            .predicted_value
                        )
                      : "—"}
                  </strong>
                </div>

                <div className="prediction-badge">
                  <Gauge size={16} />
                  ML prediction
                </div>
              </div>
            </Card>
          </div>

          <Card title="Recommended next steps">
            <div className="recommendations">
              {(
                profile.recommendations
                  ?.recommendations || []
              ).map((r, i) => (
                <div
                  key={r.product_id}
                  className="recommendation"
                >
                  <span>
                    {String(i + 1).padStart(2, "0")}
                  </span>

                  <div>
                    <b>Product opportunity</b>
                    <small className="mono">
                      {r.product_id}
                    </small>
                  </div>

                  <strong>
                    {r.score} signal
                  </strong>
                </div>
              ))}

              {!(
                profile.recommendations
                  ?.recommendations || []
              ).length && (
                <Empty
                  label={
                    profile.recommendations?.status ||
                    "No recommendations available."
                  }
                />
              )}
            </div>

            <div className="insights-box">
              <Sparkles size={17} />

              <div>
                <b>Customer story</b>

                {(profile.insights || []).map(
                  (x, i) => (
                    <p key={i}>{x}</p>
                  )
                )}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}

/* =========================================================
   OPERATIONS
========================================================= */

function Operations() {
  const [delivery, setDelivery] = useState(null);
  const [products, setProducts] = useState(null);
  const [sat, setSat] = useState(null);

  useEffect(() => {
    Promise.all([
      api("/api/analytics/delivery"),
      api("/api/analytics/products"),
      api("/api/analytics/satisfaction"),
    ])
      .then(
        ([
          deliveryData,
          productData,
          satisfaction,
        ]) => {
          setDelivery(deliveryData);
          setProducts(productData);
          setSat(satisfaction);
        }
      )
      .catch(() => {});
  }, []);

  if (!delivery) {
    return (
      <Loading label="Analysing operations..." />
    );
  }

  /*
    Convert database-style category names into
    readable dashboard labels while preserving
    the original revenue values.
  */
  const revenueCategories = (
    products?.top_categories_by_revenue || []
  )
    .slice(0, 8)
    .map((x) => ({
      ...x,
      display_category: String(
        x.category || "Unknown"
      )
        .replace(/_/g, " ")
        .replace(/\b\w/g, (char) =>
          char.toUpperCase()
        ),
    }));

  return (
    <div className="page">
      <PageTitle
        eyebrow="OPERATIONS"
        title="Find friction. Fix what matters."
        sub="A clear view of fulfilment, products and customer experience."
      />

      <div className="kpi-grid three">
        <Kpi
          icon={Clock3}
          label="Average delivery"
          value={`${delivery.average_delivery_days} days`}
          note="Delivered orders"
          tone="blue"
        />

        <Kpi
          icon={Truck}
          label="Late delivery rate"
          value={pct(
            delivery.late_delivery_rate_pct
          )}
          note="Needs attention"
          tone="amber"
        />

        <Kpi
          icon={Star}
          label="Average rating"
          value={
            sat
              ? Number(
                  sat.average_review_score
                ).toFixed(2)
              : "—"
          }
          note="Out of 5"
          tone="mint"
        />
      </div>

      <div className="grid-2">
        <Card title="Where delivery needs attention">
          <div className="bars">
            {(
              delivery.worst_states_by_late_rate ||
              []
            )
              .slice(0, 8)
              .map((x) => (
                <div
                  className="bar-row"
                  key={x.state}
                >
                  <span>{x.state}</span>

                  <div>
                    <i
                      style={{
                        width: `${Math.min(
                          x.late_rate_pct * 3,
                          100
                        )}%`,
                      }}
                    />
                  </div>

                  <b>
                    {pct(x.late_rate_pct)}
                  </b>
                </div>
              ))}
          </div>
        </Card>

        <Card title="Lowest-rated product categories">
          <div className="table-head">
            <span>Category</span>
            <span>Rating</span>
          </div>

          {(sat?.lowest_rated_categories || []).map(
            (x) => (
              <div
                className="table-row"
                key={x.category}
              >
                <span>{x.category}</span>

                <b className="rating">
                  <Star size={13} />
                  {x.avg_score}
                </b>
              </div>
            )
          )}
        </Card>
      </div>

      {/* =====================================================
          TOP REVENUE CATEGORIES
      ===================================================== */}

      <Card title="Top product categories by revenue">
        <div
          className="chart-wrap"
          style={{
            height: "320px",
            minHeight: "320px",
            overflow: "hidden",
          }}
        >
          <ResponsiveContainer
            width="100%"
            height="100%"
          >
            <BarChart
              data={revenueCategories}
              layout="vertical"
              margin={{
                top: 8,
                right: 45,
                bottom: 8,
                left: 12,
              }}
              barCategoryGap="18%"
            >
              <CartesianGrid
                stroke="#edf0f5"
                horizontal={false}
              />

              <XAxis
                type="number"
                axisLine={false}
                tickLine={false}
                tick={{
                  fontSize: 10,
                  fill: "#8991a5",
                }}
                tickFormatter={(value) =>
                  `R$${Math.round(
                    Number(value) / 1000
                  )}k`
                }
              />

              <YAxis
                type="category"
                dataKey="display_category"
                width={145}
                axisLine={false}
                tickLine={false}
                tick={{
                  fontSize: 11,
                  fill: "#697287",
                }}
              />

              <Tooltip
                cursor={{
                  fill: "#f6f7fb",
                }}
                formatter={(value) => [
                  money(value),
                  "Revenue",
                ]}
                labelFormatter={(label) =>
                  label
                }
                contentStyle={{
                  border: "0",
                  borderRadius: 12,
                  boxShadow:
                    "0 10px 30px #27314a18",
                }}
              />

              <Bar
                dataKey="revenue"
                fill="#5b5ff1"
                radius={[
                  0,
                  7,
                  7,
                  0,
                ]}
                maxBarSize={30}
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </Card>
    </div>
  );
}

/* =========================================================
   AI ASSISTANT
========================================================= */

function AI() {
  const [question, setQuestion] = useState(
    "Why should I pay attention to my customers?"
  );

  const [answer, setAnswer] = useState(null);
  const [loading, setLoading] = useState(false);
  const [sqlMode, setSqlMode] = useState(false);
  const [sql, setSql] = useState("");
  const [sqlResult, setSqlResult] = useState(null);

  const ask = async () => {
    if (!question.trim()) return;

    setLoading(true);
    setAnswer(null);

    try {
      const result = await api(
        "/api/genai/ask",
        {
          method: "POST",
          body: JSON.stringify({
            question,
          }),
        }
      );

      setAnswer(result);
    } catch (e) {
      setAnswer({
        answer: e.message,
      });
    } finally {
      setLoading(false);
    }
  };

  const runSql = async () => {
    if (!sql.trim()) return;

    setLoading(true);

    try {
      const result = await api(
        "/api/genai/nl-to-sql",
        {
          method: "POST",
          body: JSON.stringify({
            question: sql,
          }),
        }
      );

      setSqlResult(result);
    } catch (e) {
      setSqlResult({
        explanation: e.message,
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page">
      <PageTitle
        eyebrow="AI BUSINESS ASSISTANT"
        title="Talk to your data."
        sub="Ask a business question. Get a concise explanation grounded in the live database."
      />

      <div className="ai-hero">
        <div className="ai-orb">
          <Sparkles size={30} />
        </div>

        <div>
          <span className="eyebrow">
            GEMINI POWERED
          </span>

          <h2>Your analyst is ready.</h2>

          <p>
            No dashboards to decode. Just ask.
          </p>
        </div>
      </div>

      <Card className="ask-card">
        <div className="ask-label">
          <Sparkles size={18} />
          Business question
        </div>

        <textarea
          value={question}
          onChange={(e) =>
            setQuestion(e.target.value)
          }
          placeholder="e.g. Which customers should we focus on?"
        />

        <div className="ask-footer">
          <div className="chips">
            {[
              "Why did revenue change?",
              "Where is delivery weakest?",
              "What should we improve?",
            ].map((x) => (
              <button
                key={x}
                onClick={() =>
                  setQuestion(x)
                }
              >
                {x}
              </button>
            ))}
          </div>

          <button
            className="primary"
            onClick={ask}
          >
            <Sparkles size={16} />
            Ask AI
          </button>
        </div>
      </Card>

      {loading && (
        <Loading label="AI is analysing your live business context..." />
      )}

      {answer && (
        <Card
          title="Business answer"
          className="answer-card"
        >
          <div className="answer">
            <div className="answer-mark">
              <Sparkles size={17} />
            </div>

            <div>
              <p>{answer.answer}</p>

              <small>
                Generated from current business
                metrics. AI output should be reviewed
                before important decisions.
              </small>
            </div>
          </div>
        </Card>
      )}

      <div className="advanced-row">
        <div>
          <span className="eyebrow">
            FOR POWER USERS
          </span>

          <h3>
            Explore the data with natural language
          </h3>

          <p>
            Turn a question into a read-only SQL query
            and inspect the result.
          </p>
        </div>

        <button
          className="secondary"
          onClick={() =>
            setSqlMode(!sqlMode)
          }
        >
          {sqlMode ? "Hide" : "Open"} data explorer
        </button>
      </div>

      {sqlMode && (
        <Card className="sql-card">
          <textarea
            value={sql}
            onChange={(e) =>
              setSql(e.target.value)
            }
            placeholder="e.g. Show the top 10 states by number of customers"
          />

          <button
            className="secondary"
            onClick={runSql}
          >
            Generate & run safely
          </button>

          {sqlResult && (
            <div className="sql-result">
              <div className="sql-explain">
                <b>Explanation</b>

                <p>
                  {sqlResult.explanation}
                </p>
              </div>

              <details>
                <summary>
                  Show generated SQL
                </summary>

                <pre>
                  {sqlResult.generated_sql}
                </pre>
              </details>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}

/* =========================================================
   SYSTEM HEALTH
========================================================= */

function System() {
  const [health, setHealth] = useState(null);
  const [dq, setDq] = useState(null);

  useEffect(() => {
    Promise.all([
      api("/api/health"),
      api("/api/data-quality"),
    ])
      .then(([healthData, qualityData]) => {
        setHealth(healthData);
        setDq(qualityData);
      })
      .catch(() => {});
  }, []);

  if (!health) {
    return (
      <Loading label="Checking platform health..." />
    );
  }

  return (
    <div className="page">
      <PageTitle
        eyebrow="PLATFORM HEALTH"
        title="Everything under control."
        sub="Technical health is here when you need it — without getting in the way of the business view."
      />

      <div className="health-banner">
        <div className="health-check">
          <CheckCircle2 size={22} />

          <div>
            <b>Platform operational</b>
            <span>
              API and database are responding.
            </span>
          </div>
        </div>

        <span className="status-pill">
          ONLINE
        </span>
      </div>

      <div className="grid-2">
        <Card title="AI & model services">
          <Status
            name="Customer segmentation"
            ok={
              health.ml_models?.segmentation ===
              "loaded"
            }
          />

          <Status
            name="Customer value prediction"
            ok={
              health.ml_models?.clv_pipeline ===
              "loaded"
            }
          />

          <Status
            name="Retention prediction"
            ok={
              health.ml_models?.retention_pipeline ===
              "loaded"
            }
          />

          <Status
            name="Product recommendations"
            ok={
              health.ml_models?.co_occurrence ===
              "loaded"
            }
          />

          <Status
            name="AI assistant"
            ok={health.genai_configured}
          />
        </Card>

        <Card title="Data quality">
          <div className="quality-score">
            <div className="quality-ring">
              <ShieldCheck size={28} />
            </div>

            <div>
              <strong>
                {dq?.status === "healthy"
                  ? "Healthy"
                  : "Review"}
              </strong>

              <span>
                {dq?.checks?.filter(
                  (x) => x.status === "pass"
                ).length || 0}{" "}
                of{" "}
                {dq?.checks?.length || 0} checks
                passing
              </span>
            </div>
          </div>

          {(dq?.checks || [])
            .slice(0, 5)
            .map((c) => (
              <Status
                key={c.check}
                name={c.check}
                ok={c.status === "pass"}
              />
            ))}
        </Card>
      </div>

      <div className="architecture">
        <div>
          <Database />
          <b>MySQL</b>
          <small>Live data</small>
        </div>

        <ChevronRight />

        <div>
          <Activity />
          <b>FastAPI</b>
          <small>Business services</small>
        </div>

        <ChevronRight />

        <div>
          <BrainCircuit />
          <b>ML + GenAI</b>
          <small>Intelligence layer</small>
        </div>

        <ChevronRight />

        <div>
          <LayoutDashboard />
          <b>React</b>
          <small>Decision interface</small>
        </div>
      </div>
    </div>
  );
}

/* =========================================================
   SHARED COMPONENTS
========================================================= */

function Status({ name, ok }) {
  return (
    <div className="status-row">
      <span>
        {ok ? (
          <CheckCircle2 size={16} />
        ) : (
          <AlertTriangle size={16} />
        )}
      </span>

      <b>{name}</b>

      <small>
        {ok ? "Ready" : "Needs attention"}
      </small>
    </div>
  );
}

function PageTitle({
  eyebrow,
  title,
  sub,
}) {
  return (
    <div className="page-title">
      <span className="eyebrow">
        {eyebrow}
      </span>

      <h1>{title}</h1>

      <p>{sub}</p>
    </div>
  );
}

/* =========================================================
   APP
========================================================= */

export default function App() {
  const [tab, setTab] = useState("overview");
  const [mobile, setMobile] = useState(false);

  const nav = [
    [
      "overview",
      "Overview",
      LayoutDashboard,
    ],
    [
      "customers",
      "Customers",
      Users,
    ],
    [
      "customer360",
      "Customer 360",
      UserRound,
    ],
    [
      "operations",
      "Operations",
      Truck,
    ],
    [
      "ai",
      "AI Assistant",
      Sparkles,
    ],
    [
      "system",
      "System health",
      ShieldCheck,
    ],
  ];

  const content = useMemo(
    () => ({
      overview: (
        <Overview go={setTab} />
      ),

      customers: (
        <Customers
          openCustomer={() =>
            setTab("customer360")
          }
        />
      ),

      customer360: <Customer360 />,

      operations: <Operations />,

      ai: <AI />,

      system: <System />,
    }[tab]),
    [tab]
  );

  return (
    <div className="app">
      <aside
        className={`sidebar ${
          mobile ? "mobile-open" : ""
        }`}
      >
        <div className="brand">
          <div className="brand-mark">
            <Sparkles size={19} />
          </div>

          <div>
            <b>Customer</b>
            <strong>Intelligence</strong>
          </div>

          <button
            className="close-nav"
            onClick={() =>
              setMobile(false)
            }
          >
            <X size={18} />
          </button>
        </div>

        <div className="nav-label">
          WORKSPACE
        </div>

        <nav>
          {nav.map(
            ([id, label, Icon]) => (
              <button
                key={id}
                className={
                  tab === id
                    ? "nav-item selected"
                    : "nav-item"
                }
                onClick={() => {
                  setTab(id);
                  setMobile(false);
                }}
              >
                <ShellIcon
                  icon={Icon}
                  active={tab === id}
                />

                <span>{label}</span>

                {id === "ai" && (
                  <i className="new-badge">
                    AI
                  </i>
                )}
              </button>
            )
          )}
        </nav>

        <div className="sidebar-bottom">
          <div className="powered">
            <div className="mini-logo">
              <Zap size={15} />
            </div>

            <div>
              <b>Live intelligence</b>
              <small>
                Connected to MySQL
              </small>
            </div>

            <span className="live-dot" />
          </div>

          <div className="creator-credit">
            <span>
              Designed & Built by
            </span>

            <strong>
              Krishna B M
            </strong>
          </div>

          <div className="version">
            Customer Intelligence Platform · v2
          </div>
        </div>
      </aside>

      {mobile && (
        <div
          className="overlay"
          onClick={() =>
            setMobile(false)
          }
        />
      )}

      <main className="main">
        <header className="topbar">
          <button
            className="menu-btn"
            onClick={() =>
              setMobile(true)
            }
          >
            <Menu size={20} />
          </button>

          <div className="crumb">
            <span>Workspace</span>

            <ChevronRight size={14} />

            <b>
              {
                nav.find(
                  (x) => x[0] === tab
                )?.[1]
              }
            </b>
          </div>

          <div className="top-actions">
            <span className="connected">
              <i className="live-dot" />
              Live
            </span>

            <div className="user">
              <span>CI</span>
            </div>
          </div>
        </header>

        {content}

        <footer>
          Customer Intelligence Platform{" "}
          <span>•</span>{" "}
          Real data · Machine Learning · Generative AI
        </footer>
      </main>
    </div>
  );
}