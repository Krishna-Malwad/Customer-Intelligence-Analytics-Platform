import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  AreaChart, Area, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Legend,
} from "recharts";
import {
  Activity, AlertCircle, ArrowDownRight, ArrowRight, ArrowUpRight, BarChart3,
  Bot, Boxes, CheckCircle2, ChevronDown, ChevronRight, BrainCircuit, LayoutDashboard, CircleGauge, Clock3, Database,
  Gauge, HeartPulse, Home, Lightbulb, Link2, MapPin, MessageSquare, Package,
  RefreshCw, Search, Server, ShieldCheck, Sparkles, Star, Truck, Upload, UserRound,
  Users, X, Zap,
} from "lucide-react";
import "./index.css";

const API_BASE = process.env.REACT_APP_API_URL || "http://localhost:8000";

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed (${res.status})`);
  }

  return res.json();
}

async function apiPost(path, payload) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const body = await res.json().catch(() => ({}));

  if (!res.ok) {
    throw new Error(body.detail || `Request failed (${res.status})`);
  }

  return body;
}

const money = (n) =>
  `R$${Number(n || 0).toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const pct = (n) => `${Number(n || 0).toFixed(2)}%`;

const shortMoney = (n) => {
  const v = Number(n || 0);

  if (v >= 1_000_000) {
    return `R$${(v / 1_000_000).toFixed(1)}M`;
  }

  if (v >= 1_000) {
    return `R$${(v / 1_000).toFixed(0)}K`;
  }

  return `R$${v.toFixed(0)}`;
};

const COLORS = [
  "#3b82f6",
  "#22c55e",
  "#8b5cf6",
  "#f59e0b",
  "#ec4899",
  "#14b8a6",
];

const NAV = [
  ["overview", "Overview", Home],
  ["customers", "Customers", Users],
  ["customer360", "Customer 360", UserRound],
  ["operations", "Operations", Truck],
  ["ai", "AI Assistant", Sparkles],
  ["health", "System Health", ShieldCheck],
];

function Loading({ text = "Loading intelligence..." }) {
  return (
    <div className="loading">
      <RefreshCw size={16} className="spin" /> {text}
    </div>
  );
}

function ErrorBox({ message }) {
  return (
    <div className="error-box">
      <AlertCircle size={17} />
      <span>{message}</span>
    </div>
  );
}

function Card({ children, className = "", title, icon: Icon }) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="card-title">
          {Icon && <Icon size={17} />}
          <span>{title}</span>
        </div>
      )}
      {children}
    </section>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  sub,
  tone = "blue",
  trend,
  trendGood = true,
}) {
  return (
    <div className="metric-card">
      <div className={`metric-icon ${tone}`}>
        <Icon size={18} />
      </div>

      <div className="metric-copy">
        <div className="metric-label">{label}</div>
        <div className="metric-value">{value}</div>

        {trend ? (
          <div className={`metric-trend ${trendGood ? "good" : "bad"}`}>
            {trend}
          </div>
        ) : (
          <div className="metric-sub">{sub}</div>
        )}
      </div>
    </div>
  );
}

function PageHeader({ eyebrow, title, subtitle, children }) {
  return (
    <div className="page-header">
      <div>
        <div className="eyebrow">{eyebrow}</div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>

      {children}
    </div>
  );
}

function Shell({ tab, setTab, children }) {
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Activity size={20} />
          </div>

          <div>
            Customer
            <br />
            Intelligence
          </div>
        </div>

        <div className="workspace-label">Workspace</div>

        <nav>
          {NAV.map(([id, label, Icon]) => (
            <button
              key={id}
              className={`nav-item ${tab === id ? "active" : ""}`}
              onClick={() => setTab(id)}
            >
              <Icon size={18} />

              <span>{label}</span>

              {id === "ai" && <b className="nav-badge">M</b>}
            </button>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <div className="live-box">
            <span className="live-dot" />

            <div>
              <strong>Live intelligence</strong>
              <small>Connected to MySQL</small>
            </div>
          </div>

          <div className="creator">
            <span>𝐃𝐄𝐒𝐈𝐆𝐍𝐄𝐃 &amp; 𝐁𝐔𝐈𝐋𝐓 𝐁𝐘</span>
            <strong>𝐊𝐫𝐢𝐬𝐡𝐧𝐚 𝐁.𝐌</strong>
          </div>

          <div className="version">
            Customer Intelligence Platform · v2
          </div>
        </div>
      </aside>

      <main className="main-area">
        <header className="topbar">
          <div className="crumb">
            Workspace <span>›</span>{" "}
            <b>{NAV.find((x) => x[0] === tab)?.[1]}</b>
          </div>

          <div className="top-actions">
            <span className="live-text">
              <i /> Live
            </span>

            

            
          </div>
        </header>

        <div className="page-content">{children}</div>
      </main>
    </div>
  );
}

function Overview({ goAI }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      apiGet("/api/analytics/overview"),
      apiGet("/api/analytics/revenue-trend"),
      apiGet("/api/analytics/customers"),
      apiGet("/api/analytics/delivery"),
      apiGet("/api/analytics/satisfaction"),
      apiGet("/api/analytics/products"),
    ])
      .then(
        ([
          overview,
          trend,
          customers,
          delivery,
          satisfaction,
          products,
        ]) => {
          setData({
            overview,
            trend: trend.trend || [],
            customers,
            delivery,
            satisfaction,
            products,
          });
        }
      )
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return <ErrorBox message={error} />;
  }

  if (!data) {
    return <Loading text="Loading business overview..." />;
  }

  const repeat = Number(data.customers.repeat_rate_pct || 0);
  const review = Number(
    data.satisfaction.average_review_score || 0
  );
  const late = Number(
    data.delivery.late_delivery_rate_pct || 0
  );
  const avgDelivery = Number(
    data.delivery.average_delivery_days || 0
  );

  const reviewTotal = Number(
    data.satisfaction.total_reviews || 1
  );

  const distribution = Object.entries(
    data.satisfaction.score_distribution || {}
  ).map(([score, count]) => ({
    score: `${score} Star`,
    count: Number(
      ((Number(count || 0) / reviewTotal) * 100).toFixed(1)
    ),
  }));

  const latest = data.trend.length
    ? Number(
        data.trend[data.trend.length - 1]?.revenue || 0
      )
    : 0;

  const previous =
    data.trend.length > 1
      ? Number(
          data.trend[data.trend.length - 2]?.revenue || 0
        )
      : 0;

  const revenueChange = previous
    ? ((latest - previous) / previous) * 100
    : 0;

  const topCategories = (
    data.products.top_categories_by_revenue || []
  ).slice(0, 5);

  const segmentMix = [
    {
      name: "Standard",
      count: 35695,
      color: "#3b82f6",
    },
    {
      name: "High-Value",
      count: 27855,
      color: "#20b486",
    },
    {
      name: "At-Risk / Dormant",
      count: 27007,
      color: "#f59e0b",
    },
    {
      name: "Loyal / Repeat",
      count: 2801,
      color: "#7c5ce6",
    },
  ];

  const segmentedTotal = segmentMix.reduce(
    (sum, item) => sum + item.count,
    0
  );

  const attention = [
    {
      tone: "red",
      icon: AlertCircle,
      title: "High late-delivery pressure",
      text: `${pct(
        late
      )} of delivered orders were late. Prioritize the highest-risk states.`,
    },
    {
      tone: "gold",
      icon: Star,
      title: "Customer experience opportunity",
      text: `Average review score is ${review.toFixed(
        2
      )}/5 across ${data.satisfaction.total_reviews.toLocaleString()} reviews.`,
    },
    {
      tone: "blue",
      icon: BarChart3,
      title: "Revenue concentration",
      text: topCategories[0]
        ? `${topCategories[0].category} is the leading revenue category in the current data.`
        : "Review category revenue concentration.",
    },
    {
      tone: "purple",
      icon: Users,
      title: "Repeat-purchase opportunity",
      text: `${pct(
        repeat
      )} of customers purchased more than once. Retention is the clearest growth opportunity.`,
    },
  ];

  return (
    <>
      <div className="overview-hero">
        <div className="overview-hero-copy">
          <div className="overview-live-label">
            <span className="live-dot" /> LIVE BUSINESS INTELLIGENCE
          </div>

          <h1>
            <span>Know your customers.</span>
            <span className="grow-confidence">Grow with confidence.</span>
          </h1>

          <p>
            A decision-ready view of revenue, customers, delivery and
            customer experience — powered by your live data.
          </p>
        </div>

        <div className="period-pill">
          <Clock3 size={16} />
          Last 12 months
          <ChevronDown size={14} />
        </div>
      </div>

      <div className="metric-grid seven overview-kpis">
        <MetricCard
          icon={Users}
          tone="blue"
          label="Unique Customers"
          value={data.customers.total_customers.toLocaleString()}
          sub={`${segmentedTotal.toLocaleString()} in RFM segmentation`}
        />

        <MetricCard
          icon={Database}
          tone="green"
          label="Delivered Revenue"
          value={money(data.overview.total_revenue)}
          sub="Delivered orders"
        />

        <MetricCard
          icon={BarChart3}
          tone="purple"
          label="Average Order Value"
          value={money(data.overview.average_order_value)}
          sub="Per delivered order"
        />

        <MetricCard
          icon={Truck}
          tone="gold"
          label="Average Delivery Time"
          value={`${avgDelivery.toFixed(2)} days`}
          sub="Delivered orders"
        />

        <MetricCard
          icon={AlertCircle}
          tone="pink"
          label="Late-Delivery Rate"
          value={pct(late)}
          sub="Delivered orders late"
        />

        <MetricCard
          icon={Star}
          tone="blue"
          label="Average Review Score"
          value={`${review.toFixed(2)} / 5`}
          sub={`${data.satisfaction.total_reviews.toLocaleString()} reviews`}
        />

        <MetricCard
          icon={RefreshCw}
          tone="purple"
          label="Repeat-Purchase Rate"
          value={pct(repeat)}
          sub={`${data.customers.repeat_customers.toLocaleString()} repeat customers`}
        />
      </div>

      <div className="overview-row three">
        <Card
          title="Revenue Trend"
          icon={BarChart3}
          className="overview-panel revenue-panel"
        >
          <div className="panel-legend">
            <span>
              <i className="legend-blue" /> Revenue (R$)
            </span>
          </div>

          <ResponsiveContainer width="100%" height={205}>
            <LineChart
              data={data.trend}
              margin={{
                top: 10,
                right: 8,
                left: 0,
                bottom: 0,
              }}
            >
              <CartesianGrid
                stroke="#edf1f7"
                vertical={false}
              />

              <XAxis
                dataKey="month"
                tick={{
                  fontSize: 9,
                  fill: "#60708c",
                }}
                axisLine={false}
                tickLine={false}
              />

              <YAxis
                tick={{
                  fontSize: 9,
                  fill: "#60708c",
                }}
                axisLine={false}
                tickLine={false}
                tickFormatter={shortMoney}
              />

              <Tooltip
                formatter={(v) => [
                  money(v),
                  "Revenue",
                ]}
              />

              <Line
                type="monotone"
                dataKey="revenue"
                stroke="#3f7ff1"
                strokeWidth={2.5}
                dot={{
                  r: 3,
                  fill: "#3f7ff1",
                  strokeWidth: 0,
                }}
                activeDot={{ r: 5 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </Card>

        <Card
          title="Customer Mix"
          icon={Users}
          className="overview-panel mix-panel"
        >
          <div className="mix-content">
            <div className="mix-donut-wrap">
              <ResponsiveContainer width="100%" height={190}>
                <PieChart>
                  <Pie
                    data={segmentMix}
                    dataKey="count"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={54}
                    outerRadius={76}
                    paddingAngle={2}
                    stroke="#fff"
                    strokeWidth={2}
                  >
                    {segmentMix.map((item) => (
                      <Cell
                        key={item.name}
                        fill={item.color}
                      />
                    ))}
                  </Pie>

                  <Tooltip
                    formatter={(v) => [
                      Number(v).toLocaleString(),
                      "Customers",
                    ]}
                  />
                </PieChart>
              </ResponsiveContainer>

              <div className="donut-center">
                <strong>
                  {segmentedTotal.toLocaleString()}
                </strong>
                <span>RFM Customers</span>
              </div>
            </div>

            <div className="mix-legend">
              {segmentMix.map((item) => (
                <div key={item.name}>
                  <span>
                    <i style={{ background: item.color }} />
                    {item.name}
                  </span>

                  <b>
                    {(
                      (item.count / segmentedTotal) *
                      100
                    ).toFixed(1)}
                    %
                  </b>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card
          title="Delivery Performance"
          icon={Truck}
          className="overview-panel delivery-panel"
        >
          <div className="delivery-content">
            <div className="delivery-donut-wrap">
              <ResponsiveContainer width="100%" height={185}>
                <PieChart>
                  <Pie
                    data={[
                      {
                        name: "On-Time",
                        value: Math.max(
                          0,
                          100 - late
                        ),
                      },
                      {
                        name: "Late",
                        value: late,
                      },
                    ]}
                    dataKey="value"
                    innerRadius={55}
                    outerRadius={75}
                    startAngle={90}
                    endAngle={-270}
                    stroke="#fff"
                    strokeWidth={2}
                  >
                    <Cell fill="#20a978" />
                    <Cell fill="#ef5350" />
                  </Pie>
                </PieChart>
              </ResponsiveContainer>

              <div className="donut-center">
                <strong>
                  {(100 - late).toFixed(1)}%
                </strong>
                <span>On-Time Delivery</span>
              </div>
            </div>

            <div className="delivery-stats">
              <div>
                <span>
                  <i className="dot green" /> On-Time
                </span>
                <b>{(100 - late).toFixed(1)}%</b>
              </div>

              <div>
                <span>
                  <i className="dot red" /> Late
                </span>
                <b>{late.toFixed(1)}%</b>
              </div>

              <div className="delivery-average">
                <Truck size={19} />
                <span>Avg. Delivery Time</span>
                <strong>
                  {avgDelivery.toFixed(2)} days
                </strong>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <div className="overview-row three second-row">
        <Card
          title="Review Distribution"
          icon={Star}
          className="overview-panel review-panel"
        >
          <ResponsiveContainer width="100%" height={205}>
            <BarChart
              data={distribution}
              margin={{
                top: 10,
                right: 4,
                left: 0,
                bottom: 0,
              }}
            >
              <CartesianGrid
                stroke="#edf1f7"
                vertical={false}
              />

              <XAxis
                dataKey="score"
                tick={{
                  fontSize: 8.5,
                  fill: "#60708c",
                }}
                axisLine={false}
                tickLine={false}
              />

              <YAxis
                tick={{
                  fontSize: 9,
                  fill: "#60708c",
                }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v) => `${v}%`}
              />

              <Tooltip
                formatter={(v) => [
                  `${Number(v).toFixed(1)}%`,
                  "Reviews",
                ]}
              />

              <Bar
                dataKey="count"
                fill="#38a875"
                radius={[5, 5, 0, 0]}
                barSize={36}
              />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card
          title="Top Product Categories by Revenue"
          icon={Package}
          className="overview-panel category-panel"
        >
          <div className="category-bars">
            {topCategories.map((item) => {
              const max = Number(
                topCategories[0]?.revenue || 1
              );

              const value = Number(
                item.revenue || 0
              );

              return (
                <div
                  className="category-bar-row"
                  key={item.category}
                >
                  <span>{item.category}</span>

                  <div>
                    <i
                      style={{
                        width: `${Math.max(
                          8,
                          (value / max) * 100
                        )}%`,
                      }}
                    />
                  </div>

                  <b>{shortMoney(value)}</b>
                </div>
              );
            })}
          </div>
        </Card>

        <Card
          title="Business Attention Areas"
          icon={Lightbulb}
          className="overview-panel attention-panel"
        >
          <div className="attention-list">
            {attention.map(
              ({
                tone,
                icon: Icon,
                title,
                text,
              }) => (
                <div
                  className="attention-row"
                  key={title}
                >
                  <div
                    className={`attention-badge ${tone}`}
                  >
                    <Icon size={15} />
                  </div>

                  <div>
                    <b>{title}</b>
                    <span>{text}</span>
                  </div>
                </div>
              )
            )}
          </div>
        </Card>
      </div>

      <Card
        title="Recent Insights"
        icon={Lightbulb}
        className="recent-insights-card"
      >
        <div className="recent-insights-grid">
          <div className="recent-insight green">
            <div className="recent-icon">
              <ArrowUpRight size={18} />
            </div>

            <div>
              <b>Revenue Growth</b>
              <span>
                Latest delivered revenue is{" "}
                {revenueChange >= 0 ? "up" : "down"}{" "}
                {Math.abs(revenueChange).toFixed(
                  1
                )}
                % versus the previous month.
              </span>
            </div>
          </div>

          <div className="recent-insight blue">
            <div className="recent-icon">
              <Users size={18} />
            </div>

            <div>
              <b>Customer Segment</b>

              <span>
                High-Value customers represent{" "}
                {(
                  (27855 / segmentedTotal) *
                  100
                ).toFixed(1)}
                % of the RFM-segmented customer base.
              </span>
            </div>
          </div>

          <div className="recent-insight purple">
            <div className="recent-icon">
              <Truck size={18} />
            </div>

            <div>
              <b>Delivery Performance</b>

              <span>
                On-time delivery is{" "}
                {(100 - late).toFixed(1)}%, with
                average delivery time of{" "}
                {avgDelivery.toFixed(2)} days.
              </span>
            </div>
          </div>

          <div className="recent-insight gold">
            <div className="recent-icon">
              <Star size={18} />
            </div>

            <div>
              <b>Review Performance</b>

              <span>
                Five-star reviews account for{" "}
                {Number(
                  distribution.find(
                    (item) =>
                      item.score === "5 Star"
                  )?.count || 0
                ).toFixed(1)}
                % of all reviews.
              </span>
            </div>
          </div>
        </div>
      </Card>
    </>
  );
}

function Customers() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  /*
   * IMPORTANT:
   * The effect callback itself does NOT return the Promise.
   * This prevents React's "destroy is not a function" error.
   */
  useEffect(() => {
    apiGet("/api/analytics/customers")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return <ErrorBox message={error} />;
  }

  if (!data) {
    return (
      <Loading text="Loading customer intelligence..." />
    );
  }

  const segmented = 93358;
  const highValue = 27855;

  return (
    <>
      <PageHeader
        eyebrow="Customer intelligence"
        title="Understand your customers."
        subtitle="Explore customer demographics, behaviour, segments and geographic distribution."
      />

      <div className="metric-grid five customer-kpis">
        <MetricCard
          icon={Users}
          tone="blue"
          label="Total customers"
          value={data.total_customers.toLocaleString()}
          sub="Unique customer identities"
        />

        <MetricCard
          icon={CircleGauge}
          tone="purple"
          label="RFM segmented"
          value={segmented.toLocaleString()}
          sub="Customers scored by RFM"
        />

        <MetricCard
          icon={RefreshCw}
          tone="green"
          label="Repeat customers"
          value={data.repeat_customers.toLocaleString()}
          sub={`${pct(
            data.repeat_rate_pct
          )} repeat rate`}
        />

        <MetricCard
          icon={Star}
          tone="gold"
          label="Customer satisfaction"
          value="4.09 / 5"
          sub="Average review score"
        />

        <MetricCard
          icon={Zap}
          tone="pink"
          label="High-value customers"
          value={highValue.toLocaleString()}
          sub="RFM high-value segment"
        />
      </div>

      <div className="customers-reference-grid">
        <Card
          title="Customer segmentation"
          icon={CircleGauge}
        >
          <div className="segment-summary">
            {[
              ["Standard", 35695, "blue"],
              ["High-Value", 27855, "green"],
              [
                "At-Risk / Dormant",
                27007,
                "gold",
              ],
              [
                "Loyal / Repeat",
                2801,
                "purple",
              ],
            ].map(
              ([name, count, tone]) => (
                <div
                  className="segment-line"
                  key={name}
                >
                  <span>
                    <i
                      className={`seg-dot ${tone}`}
                    />
                    {name}
                  </span>

                  <b>{count.toLocaleString()}</b>
                </div>
              )
            )}
          </div>
        </Card>

        <Card
          title="Customer geography"
          icon={MapPin}
        >
          <div className="state-list">
            {(data.top_states || [])
              .slice(0, 8)
              .map((s, i) => (
                <div
                  className="state-row"
                  key={s.state}
                >
                  <span className="rank">
                    {String(i + 1).padStart(
                      2,
                      "0"
                    )}
                  </span>

                  <b>{s.state}</b>

                  <div className="state-bar">
                    <span
                      style={{
                        width: `${Math.max(
                          4,
                          (s.customers /
                            data.top_states[0]
                              .customers) *
                            100
                        )}%`,
                      }}
                    />
                  </div>

                  <strong>
                    {Number(
                      s.customers
                    ).toLocaleString()}
                  </strong>
                </div>
              ))}
          </div>
        </Card>

        <Card
          title="Customer growth trend"
          icon={ArrowUpRight}
        >
          <div className="growth-placeholder">
            <div className="growth-line">
              <span />
              <span />
              <span />
              <span />
              <span />
              <span />
            </div>

            <b>Live customer analytics</b>

            <p>
              Use the customer history and
              repeat-purchase signals to monitor
              growth over time.
            </p>
          </div>
        </Card>
      </div>

      <div className="customers-bottom-grid">
        <Card
          title="Customer segments"
          icon={Users}
        >
          <div className="table-list">
            {[
              [
                "Standard",
                "35,695",
                "38.2%",
              ],
              [
                "High-Value",
                "27,855",
                "29.8%",
              ],
              [
                "At-Risk / Dormant",
                "27,007",
                "28.9%",
              ],
              [
                "Loyal / Repeat",
                "2,801",
                "3.0%",
              ],
            ].map(
              ([name, count, share], i) => (
                <div
                  className="table-row"
                  key={name}
                >
                  <span className="rank">
                    {i + 1}
                  </span>

                  <b>{name}</b>

                  <strong>{count}</strong>

                  <small>{share}</small>
                </div>
              )
            )}
          </div>
        </Card>

        <Card
          title="Top locations"
          icon={MapPin}
        >
          <div className="table-list">
            {(data.top_states || [])
              .slice(0, 6)
              .map((s, i) => (
                <div
                  className="table-row"
                  key={s.state}
                >
                  <span className="rank">
                    {i + 1}
                  </span>

                  <b>{s.state}</b>

                  <strong>
                    {Number(
                      s.customers
                    ).toLocaleString()}
                  </strong>

                  <small>customers</small>
                </div>
              ))}
          </div>
        </Card>

        <Card
          title="Customer insights"
          icon={Lightbulb}
        >
          <div className="insight-stack">
            <div>
              <Users size={18} />

              <p>
                <b>Repeat purchase</b>{" "}
                remains a key growth opportunity
                in the current customer base.
              </p>
            </div>

            <div>
              <Zap size={18} />

              <p>
                <b>High-value customers</b> form
                a meaningful share of the
                RFM-segmented population.
              </p>
            </div>

            <div>
              <MapPin size={18} />

              <p>
                <b>
                  {data.top_states?.[0]?.state ||
                    "Top state"}
                </b>{" "}
                has the largest customer
                concentration among the leading
                states.
              </p>
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}

function Customer360() {
  const [id, setId] = useState("");
  const [profile, setProfile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const search = async () => {
    if (!id.trim()) return;

    setLoading(true);
    setError(null);
    setProfile(null);

    try {
      setProfile(
        await apiGet(
          `/api/customers/${encodeURIComponent(
            id.trim()
          )}`
        )
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <PageHeader
        eyebrow="Customer intelligence"
        title="Know one customer deeply."
        subtitle="Explore a complete view of a customer’s history, value, behaviour and next-best actions."
      />

      <div className="customer-search">
        <Search size={18} />

        <input
          value={id}
          onChange={(e) => setId(e.target.value)}
          onKeyDown={(e) =>
            e.key === "Enter" && search()
          }
          placeholder="Search customer ID..."
        />

        <button onClick={search}>
          View customer
          <ArrowRight size={15} />
        </button>
      </div>

      {loading && (
        <Loading text="Fetching customer profile..." />
      )}

      {error && <ErrorBox message={error} />}

      {profile && (
        <CustomerProfile profile={profile} />
      )}

      {!profile &&
        !loading &&
        !error && (
          <div className="empty-c360">
            <div className="empty-icon">
              <UserRound size={28} />
            </div>

            <h2>Search a real customer</h2>

            <p>
              Enter a customer_unique_id to load
              live purchase history, value, ML
              predictions and recommendations.
            </p>
          </div>
        )}
    </>
  );
}

function CustomerProfile({ profile }) {
  const seg =
    profile.segment?.segment_cluster ??
    profile.segment?.status ??
    "—";

  const retention =
    profile.retention_prediction?.probability !=
    null
      ? `${(
          profile.retention_prediction
            .probability * 100
        ).toFixed(1)}%`
      : profile.retention_prediction?.status;

  const predicted =
    profile.predicted_next_order_value
      ?.predicted_value != null
      ? money(
          profile.predicted_next_order_value
            .predicted_value
        )
      : profile.predicted_next_order_value
          ?.status;

  return (
    <>
      <div className="customer-banner">
        <div className="customer-avatar">
          {String(
            profile.customer_unique_id || "CI"
          )
            .slice(0, 2)
            .toUpperCase()}
        </div>

        <div className="customer-id">
          <span>Customer ID</span>

          <b>{profile.customer_unique_id}</b>

          <em>{seg}</em>
        </div>

        <div className="customer-meta">
          <span>
            <MapPin size={15} />
            {profile.state || "—"} ·{" "}
            {profile.city || "—"}
          </span>

          <span>
            <Clock3 size={15} />
            Since{" "}
            {profile.first_purchase_date ||
              "—"}
          </span>
        </div>

        <div className="segment">
          <span>Predicted segment</span>
          <b>{seg}</b>
        </div>
      </div>

      <div className="metric-grid five">
        <MetricCard
          icon={Package}
          tone="blue"
          label="Delivered orders"
          value={profile.order_count ?? "—"}
          sub="Customer orders"
        />

        <MetricCard
          icon={BarChart3}
          tone="green"
          label="Total customer value"
          value={money(profile.total_revenue)}
          sub="Delivered revenue"
        />

        <MetricCard
          icon={TagIcon}
          tone="purple"
          label="Average order value"
          value={money(
            profile.average_order_value
          )}
          sub="Average order"
        />

        <MetricCard
          icon={Clock3}
          tone="gold"
          label="Recency"
          value={`${profile.rfm?.recency_days ?? "—"} days`}
          sub="Since last purchase"
        />

        <MetricCard
          icon={RefreshCw}
          tone="pink"
          label="Retention probability"
          value={retention || "—"}
          sub="Model prediction"
        />
      </div>

      <div className="three-grid customer-lower">
        <Card
          title="ML predictions"
          icon={Sparkles}
        >
          <div className="prediction-row">
            <span>Segment</span>
            <b>{seg}</b>
          </div>

          <div className="prediction-row">
            <span>Retention</span>
            <b>{retention || "—"}</b>
          </div>

          <div className="prediction-row">
            <span>Next order value</span>
            <b>{predicted || "—"}</b>
          </div>
        </Card>

        <Card
          title="Next-best actions"
          icon={Lightbulb}
        >
          <ul className="clean-list">
            {(
              profile.recommendations
                ?.recommendations || []
            )
              .slice(0, 5)
              .map((r, i) => (
                <li key={i}>
                  <span>{i + 1}</span>

                  <div>
                    <b>{r.product_id}</b>
                    <small>
                      Recommendation score{" "}
                      {r.score}
                    </small>
                  </div>
                </li>
              ))}
          </ul>

          {(!profile.recommendations
            ?.recommendations ||
            profile.recommendations
              .recommendations.length === 0) && (
            <p className="muted">
              {profile.recommendations?.status ||
                "No recommendations available."}
            </p>
          )}
        </Card>

        <Card
          title="Customer story"
          icon={MessageSquare}
        >
          <ul className="insights">
            {(profile.insights || []).map(
              (x, i) => (
                <li key={i}>{x}</li>
              )
            )}
          </ul>
        </Card>
      </div>
    </>
  );
}

function TagIcon(props) {
  return <Boxes {...props} />;
}

function Operations() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  /*
   * IMPORTANT:
   * The effect callback does NOT directly return Promise.all().
   * This fixes React's "destroy is not a function" error.
   */
  useEffect(() => {
    Promise.all([
      apiGet("/api/analytics/delivery"),
      apiGet("/api/analytics/products"),
      apiGet("/api/analytics/satisfaction"),
    ])
      .then(
        ([delivery, products, satisfaction]) => {
          setData({
            delivery,
            products,
            satisfaction,
          });
        }
      )
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return <ErrorBox message={error} />;
  }

  if (!data) {
    return (
      <Loading text="Loading operations analytics..." />
    );
  }

  const worst =
    data.delivery.worst_states_by_late_rate ||
    [];

  const cats =
    data.satisfaction.lowest_rated_categories ||
    [];

  const top =
    data.products.top_categories_by_revenue ||
    [];

  const late = Number(
    data.delivery.late_delivery_rate_pct || 0
  );

  const avgDelivery = Number(
    data.delivery.average_delivery_days || 0
  );

  return (
    <>
      <PageHeader
        eyebrow="Operations"
        title="Operations Analytics"
        subtitle="Monitor fulfillment performance, delivery health and customer satisfaction."
      />

      <div className="metric-grid four">
        <MetricCard
          icon={Truck}
          tone="blue"
          label="Average delivery time"
          value={`${avgDelivery.toFixed(2)} days`}
          sub="Delivered orders"
        />

        <MetricCard
          icon={AlertCircle}
          tone="pink"
          label="Late-delivery rate"
          value={pct(late)}
          sub="Delivered orders late"
        />

        <MetricCard
          icon={CheckCircle2}
          tone="green"
          label="On-time delivery rate"
          value={`${(100 - late).toFixed(1)}%`}
          sub="Delivered orders on time"
        />

        <MetricCard
          icon={Star}
          tone="gold"
          label="Average review score"
          value={`${Number(
            data.satisfaction
              .average_review_score
          ).toFixed(2)} / 5`}
          sub={`${Number(
            data.satisfaction.total_reviews
          ).toLocaleString()} reviews`}
        />
      </div>

      <div className="operations-reference-top">
        <Card
          title="Delivery performance"
          icon={Truck}
        >
          <div className="ops-trend">
            <div className="ops-bars">
              {[...worst]
                .slice(0, 8)
                .reverse()
                .map((s) => (
                  <div
                    key={s.state}
                    style={{
                      height: `${Math.max(
                        14,
                        Math.min(
                          100,
                          Number(
                            s.late_rate_pct
                          ) * 4
                        )
                      )}%`,
                    }}
                  />
                ))}
            </div>

            <div className="ops-axis">
              <span>Low</span>
              <span>Late-delivery rate</span>
              <span>High</span>
            </div>
          </div>
        </Card>

        <Card
          title="Delivery performance by state"
          icon={MapPin}
        >
          <div className="horizontal-bars">
            {worst.slice(0, 8).map((s) => (
              <div
                className="hbar"
                key={s.state}
              >
                <div>
                  <b>{s.state}</b>
                  <span>
                    {pct(s.late_rate_pct)}
                  </span>
                </div>

                <div className="bar-track">
                  <i
                    style={{
                      width: `${Math.min(
                        100,
                        s.late_rate_pct * 4
                      )}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </Card>

        <Card
          title="Delivery time distribution"
          icon={Clock3}
        >
          <div className="delivery-distribution">
            <div className="distribution-ring">
              <strong>
                {avgDelivery.toFixed(2)}
              </strong>

              <span>avg days</span>
            </div>

            <div className="distribution-legend">
              <span>
                <i className="dot green" />
                On-time
              </span>

              <b>
                {(100 - late).toFixed(1)}%
              </b>

              <span>
                <i className="dot red" />
                Late
              </span>

              <b>{late.toFixed(1)}%</b>
            </div>
          </div>
        </Card>
      </div>

      <div className="operations-reference-bottom">
        <Card
          title="Lowest rated product categories"
          icon={Star}
        >
          <div className="table-list">
            {cats.slice(0, 6).map((c, i) => (
              <div
                className="table-row"
                key={c.category}
              >
                <span className="rank">
                  {i + 1}
                </span>

                <b>{c.category}</b>

                <strong>
                  {Number(
                    c.avg_score
                  ).toFixed(2)}
                </strong>

                <small>
                  {Number(
                    c.n_reviews
                  ).toLocaleString()}{" "}
                  reviews
                </small>
              </div>
            ))}
          </div>
        </Card>

        <Card
          title="Revenue by product category"
          icon={BarChart3}
        >
          <div className="category-bars">
            {top.slice(0, 6).map((item) => (
              <div
                className="category-bar-row"
                key={item.category}
              >
                <span>{item.category}</span>

                <div>
                  <i
                    style={{
                      width: `${Math.max(
                        8,
                        (Number(
                          item.revenue
                        ) /
                          Number(
                            top[0]?.revenue ||
                              1
                          )) *
                          100
                      )}%`,
                    }}
                  />
                </div>

                <b>
                  {shortMoney(
                    item.revenue
                  )}
                </b>
              </div>
            ))}
          </div>
        </Card>

        <Card
          title="Operational insights"
          icon={Lightbulb}
        >
          <div className="insight-stack">
            <div>
              <AlertCircle size={18} />

              <p>
                <b>
                  {worst[0]?.state ||
                    "Top state"}
                </b>{" "}
                has the highest late-delivery
                rate among monitored states.
              </p>
            </div>

            <div>
              <Star size={18} />

              <p>
                <b>
                  {cats[0]?.category ||
                    "Lowest-rated category"}
                </b>{" "}
                has the lowest average review
                score in the current data.
              </p>
            </div>

            <div>
              <Truck size={18} />

              <p>
                Average delivery time is{" "}
                <b>
                  {avgDelivery.toFixed(2)} days
                </b>
                .
              </p>
            </div>
          </div>
        </Card>
      </div>
    </>
  );
}

const AI_PROMPTS = [
  "What is our total revenue and average order value?",
  "Which states have the highest late delivery rates?",
  "Show me our lowest-rated product categories",
  "How many repeat customers do we have?",
];

const REPORT_SECTIONS = [
  ["executive_summary", "Executive Summary"],
  ["revenue_and_customer_performance", "Revenue & Customer Performance"],
  ["product_performance", "Product Performance"],
  ["delivery_and_operations", "Delivery & Operations"],
  ["customer_satisfaction", "Customer Satisfaction"],
  ["key_findings", "Key Findings"],
  ["recommended_areas_of_attention", "Recommended Areas of Attention"],
];

function Modal({ title, icon: Icon, onClose, children, wide }) {
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div
        className={`modal-panel ${wide ? "modal-wide" : ""}`}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="modal-head">
          <div className="modal-head-title">
            {Icon && <Icon size={17} />}
            <span>{title}</span>
          </div>

          <button
            className="modal-close"
            onClick={onClose}
            aria-label="Close"
          >
            <X size={16} />
          </button>
        </div>

        <div className="modal-body">{children}</div>
      </div>
    </div>
  );
}

function SqlWorkspace({ onClose }) {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const run = async () => {
    const q = question.trim();
    if (!q || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      setResult(
        await apiPost("/api/genai/nl-to-sql", { question: q })
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const columns =
    result && result.results && result.results.length > 0
      ? Object.keys(result.results[0])
      : [];

  return (
    <Modal title="Natural Language → SQL" icon={Database} onClose={onClose} wide>
      <p className="workspace-intro">
        Ask a question in plain English. It's converted into read-only SQL,
        validated against the existing safety rules, run against the live
        database, and explained.
      </p>

      <div className="workspace-input">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="e.g. Which 5 states have the highest late-delivery rate?"
          autoFocus
        />
        <button onClick={run} disabled={loading || !question.trim()}>
          <ArrowRight size={16} />
        </button>
      </div>

      {loading && <Loading text="Generating and running SQL..." />}
      {error && <ErrorBox message={error} />}

      {!loading && !error && !result && (
        <div className="workspace-empty">
          Ask a question above to generate SQL.
        </div>
      )}

      {!loading && result && (
        <div className="sql-result">
          <div className="sql-block-label">Generated SQL</div>
          <pre className="sql-block">{result.generated_sql}</pre>

          {result.reasoning && (
            <div className="sql-reasoning">{result.reasoning}</div>
          )}

          <div className="sql-block-label">
            Result ({result.row_count}{" "}
            {result.row_count === 1 ? "row" : "rows"})
          </div>

          {columns.length > 0 ? (
            <div className="sql-table-wrap">
              <table className="sql-table">
                <thead>
                  <tr>
                    {columns.map((col) => (
                      <th key={col}>{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {result.results.map((row, i) => (
                    <tr key={i}>
                      {columns.map((col) => (
                        <td key={col}>{String(row[col])}</td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="workspace-empty">No rows returned.</div>
          )}

          {result.explanation && (
            <div className="answer-text">{result.explanation}</div>
          )}
        </div>
      )}
    </Modal>
  );
}

function InsightsWorkspace({ onClose }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);

    apiPost("/api/genai/insights", {})
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  return (
    <Modal title="Automated Insights" icon={Lightbulb} onClose={onClose} wide>
      <p className="workspace-intro">
        Trends, patterns, and anomalies pulled from the project's live
        analytics.
      </p>

      {loading && <Loading text="Analyzing the latest metrics..." />}
      {error && <ErrorBox message={error} />}

      {!loading && !error && data && (
        <div className="answer-text">{data.insights}</div>
      )}

      {!loading && !error && !data && (
        <div className="workspace-empty">No insights were returned.</div>
      )}

      <div className="workspace-actions">
        <button
          className="workspace-refresh"
          onClick={load}
          disabled={loading}
        >
          <RefreshCw size={13} /> Regenerate
        </button>
      </div>
    </Modal>
  );
}

function ReportWorkspace({ onClose }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [report, setReport] = useState(null);

  const load = () => {
    setLoading(true);
    setError(null);

    apiPost("/api/genai/report", {})
      .then((res) => setReport(res.report || null))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const sections = REPORT_SECTIONS.filter(([key]) => report && report[key]);

  return (
    <Modal title="Report Generation" icon={Boxes} onClose={onClose} wide>
      <p className="workspace-intro">
        A structured business report generated from the project's live
        analytics.
      </p>

      {loading && <Loading text="Generating report..." />}
      {error && <ErrorBox message={error} />}

      {!loading && !error && sections.length > 0 && (
        <div className="report-sections">
          {sections.map(([key, label]) => (
            <div className="report-section" key={key}>
              <b>{label}</b>
              <p>{report[key]}</p>
            </div>
          ))}
        </div>
      )}

      {!loading && !error && report && sections.length === 0 && (
        <div className="workspace-empty">
          No report content was returned.
        </div>
      )}

      <div className="workspace-actions">
        <button
          className="workspace-refresh"
          onClick={load}
          disabled={loading}
        >
          <RefreshCw size={13} /> Regenerate
        </button>
      </div>
    </Modal>
  );
}

function ChartInsightWorkspace({ onClose }) {
  const [mode, setMode] = useState("url");
  const [url, setUrl] = useState("");
  const [file, setFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const switchMode = (m) => {
    setMode(m);
    setResult(null);
    setError(null);
  };

  const analyzeUrl = async () => {
    const u = url.trim();
    if (!u || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      setResult(
        await apiPost("/api/genai/chart-insight/url", { url: u })
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  const analyzeScreenshot = async () => {
    if (!file || loading) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const formData = new FormData();
      formData.append("file", file);

      const res = await fetch(
        `${API_BASE}/api/genai/chart-insight/screenshot`,
        { method: "POST", body: formData }
      );

      const body = await res.json().catch(() => ({}));

      if (!res.ok) {
        throw new Error(body.detail || `Request failed (${res.status})`);
      }

      setResult(body);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Modal title="Dashboard Analyst" icon={BarChart3} onClose={onClose} wide>
      <p className="workspace-intro">
        Get an AI read on a dashboard — paste a public URL, or upload a
        screenshot for a closer visual analysis.
      </p>

      <div className="mode-toggle">
        <button
          className={mode === "url" ? "active" : ""}
          onClick={() => switchMode("url")}
        >
          <Link2 size={13} /> Public URL
        </button>

        <button
          className={mode === "screenshot" ? "active" : ""}
          onClick={() => switchMode("screenshot")}
        >
          <Upload size={13} /> Screenshot
        </button>
      </div>

      {mode === "url" ? (
        <div className="workspace-input">
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && analyzeUrl()}
            placeholder="https://your-public-dashboard-url..."
            autoFocus
          />
          <button onClick={analyzeUrl} disabled={loading || !url.trim()}>
            <ArrowRight size={16} />
          </button>
        </div>
      ) : (
        <div className="dropzone">
          <input
            id="chart-screenshot-input"
            type="file"
            accept="image/png,image/jpeg,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
          <label htmlFor="chart-screenshot-input">
            <Upload size={20} />
            <span>
              {file
                ? file.name
                : "Click to choose a screenshot (PNG, JPEG, or WebP, under 6 MB)"}
            </span>
          </label>
          <button
            onClick={analyzeScreenshot}
            disabled={loading || !file}
          >
            Analyze screenshot
          </button>
        </div>
      )}

      {loading && <Loading text="Analyzing the dashboard..." />}
      {error && <ErrorBox message={error} />}

      {!loading && !error && result && (
        <div className="chart-result">
          {result.fetch_note && (
            <div className="chart-note">{result.fetch_note}</div>
          )}
          <div className="answer-text">{result.analysis}</div>
        </div>
      )}
    </Modal>
  );
}

function AI() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeCapability, setActiveCapability] = useState(null);

  const [quick, setQuick] = useState(null);
  const [quickError, setQuickError] = useState(null);

  const chatInputRef = useRef(null);
  const chatEndRef = useRef(null);

  useEffect(() => {
    Promise.all([
      apiGet("/api/analytics/overview"),
      apiGet("/api/analytics/delivery"),
      apiGet("/api/analytics/satisfaction"),
      apiGet("/api/analytics/customers"),
    ])
      .then(([overview, delivery, satisfaction, customers]) => {
        setQuick({ overview, delivery, satisfaction, customers });
      })
      .catch((e) => setQuickError(e.message));
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const ask = async (q = question) => {
    const text = (q || "").trim();
    if (!text || loading) return;

    setMessages((prev) => [...prev, { role: "user", text }]);
    setQuestion("");
    setLoading(true);

    try {
      const answer = await apiPost("/api/genai/ask", { question: text });

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text:
            answer.answer ||
            answer.response ||
            answer.message ||
            JSON.stringify(answer),
        },
      ]);
    } catch (e) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", text: e.message, isError: true },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const focusChat = () => {
    chatInputRef.current?.focus();
    chatInputRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  };

  const capabilities = [
    {
      id: "chat",
      icon: Bot,
      title: "Business Analyst Assistant",
      desc: "Ask questions about customers, revenue, products, delivery, and satisfaction.",
      tone: "blue",
      onSelect: focusChat,
    },
    {
      id: "sql",
      icon: Database,
      title: "Natural Language → SQL",
      desc: "Ask a business question and generate safe, read-only SQL against the live database.",
      tone: "green",
      onSelect: () => setActiveCapability("sql"),
    },
    {
      id: "insights",
      icon: Lightbulb,
      title: "Automated Insights",
      desc: "Discover important trends, anomalies, and business signals from the latest data.",
      tone: "gold",
      onSelect: () => setActiveCapability("insights"),
    },
    {
      id: "report",
      icon: Boxes,
      title: "Report Generation",
      desc: "Generate a structured business report from the latest project analytics.",
      tone: "purple",
      onSelect: () => setActiveCapability("report"),
    },
    {
      id: "chart",
      icon: BarChart3,
      title: "Dashboard Analyst",
      desc: "Analyze a dashboard by URL or screenshot and explain trends and anomalies.",
      tone: "teal",
      onSelect: () => setActiveCapability("chart"),
    },
  ];

  const userQuestions = messages.filter((m) => m.role === "user");
  const recentQuestions = [...userQuestions].reverse().slice(0, 6);
  const showingSuggested = recentQuestions.length === 0;
  const recentItems = showingSuggested
    ? AI_PROMPTS.map((p) => ({ text: p }))
    : recentQuestions;

  const overview = quick && quick.overview;
  const delivery = quick && quick.delivery;
  const satisfaction = quick && quick.satisfaction;
  const customers = quick && quick.customers;

  return (
    <>
      <div className="ai-layout">
        <div className="ai-main">
          <div className="ai-hero">
            <div className="ai-copy">
              <div className="eyebrow">
                <Sparkles size={14} />
                AI business assistant
              </div>

              <h1>
                Ask questions.{" "}
                <span>Get insights.</span>
              </h1>

              <p>
                Grounded in your project's real database and analytics —
                not guesses.
              </p>

              <div className="ai-input">
                <Sparkles size={18} />

                <input
                  ref={chatInputRef}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && ask()}
                  placeholder="Ask anything about your business..."
                  disabled={loading}
                />

                <button onClick={() => ask()} disabled={loading || !question.trim()}>
                  <ArrowRight size={18} />
                </button>
              </div>

              <div className="prompt-label">Try asking:</div>

              <div className="prompt-chips">
                {AI_PROMPTS.map((p) => (
                  <button key={p} onClick={() => ask(p)} disabled={loading}>
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div className="ai-art">
              <div className="bot">
                <Bot size={58} />
              </div>

              <Sparkles className="spark s1" />
              <Sparkles className="spark s2" />

              <div className="floating-chart">
                <BarChart3 size={24} />
              </div>
            </div>
          </div>

          <Card className="chat-card" title="Conversation" icon={MessageSquare}>
            {messages.length === 0 && !loading ? (
              <div className="workspace-empty">
                Ask a question above to start the conversation — answers are
                grounded in the project's real business data.
              </div>
            ) : (
              <div className="chat-thread">
                {messages.map((m, i) => (
                  <div
                    key={i}
                    className={`chat-bubble ${m.role} ${m.isError ? "error" : ""}`}
                  >
                    <div className="chat-bubble-icon">
                      {m.role === "user" ? (
                        <UserRound size={13} />
                      ) : (
                        <Sparkles size={13} />
                      )}
                    </div>
                    <div className="chat-bubble-text">{m.text}</div>
                  </div>
                ))}

                {loading && (
                  <div className="chat-bubble assistant">
                    <div className="chat-bubble-icon">
                      <Sparkles size={13} />
                    </div>
                    <div className="chat-bubble-text">
                      <Loading text="Gemini is analyzing the live business context..." />
                    </div>
                  </div>
                )}

                <div ref={chatEndRef} />
              </div>
            )}
          </Card>

          <Card title="AI capabilities" icon={Sparkles}>
            <div className="cap-grid">
              {capabilities.map(({ id, icon: Icon, title, desc, tone, onSelect }) => (
                <div
                  className="cap-card"
                  key={id}
                  role="button"
                  tabIndex={0}
                  onClick={onSelect}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      onSelect();
                    }
                  }}
                >
                  <div className={`cap-icon ${tone}`}>
                    <Icon size={19} />
                  </div>

                  <b>{title}</b>

                  <p>{desc}</p>

                  <span>
                    {id === "chat" ? "Focus chat" : "Open"}{" "}
                    <ArrowRight size={13} />
                  </span>
                </div>
              ))}
            </div>
          </Card>

          <div className="how">
            <Sparkles size={20} />

            <div>
              <b>How it works</b>
              <p>Ask → analyze → receive grounded insights → take action.</p>
            </div>

            <div className="steps">
              <span>
                <i>1</i> Ask
              </span>

              <span>
                <i>2</i> Analyze
              </span>

              <span>
                <i>3</i> Get insights
              </span>

              <span>
                <i>4</i> Take action
              </span>
            </div>
          </div>
        </div>

        <aside className="ai-side">
          <Card title="Quick insights" icon={Lightbulb}>
            {quickError && <ErrorBox message={quickError} />}

            {!quickError && !quick && <Loading text="Loading metrics..." />}

            {!quickError && quick && (
              <div className="quick-list">
                <QuickMetric
                  label="Revenue"
                  value={overview ? money(overview.total_revenue) : "—"}
                  icon={BarChart3}
                />

                <QuickMetric
                  label="AOV"
                  value={overview ? money(overview.average_order_value) : "—"}
                  icon={Package}
                />

                <QuickMetric
                  label="Late delivery"
                  value={
                    delivery && delivery.late_delivery_rate_pct != null
                      ? pct(delivery.late_delivery_rate_pct)
                      : "—"
                  }
                  icon={Truck}
                />

                <QuickMetric
                  label="Avg. review"
                  value={
                    satisfaction && satisfaction.average_review_score != null
                      ? `${satisfaction.average_review_score.toFixed(2)}/5`
                      : "—"
                  }
                  icon={Star}
                />

                <QuickMetric
                  label="Repeat rate"
                  value={
                    customers && customers.repeat_rate_pct != null
                      ? pct(customers.repeat_rate_pct)
                      : "—"
                  }
                  icon={Users}
                />
              </div>
            )}
          </Card>

          <Card title="Recent conversations" icon={MessageSquare}>
            <div className="recent">
              {recentItems.map((item, i) => (
                <button
                  key={`${item.text}-${i}`}
                  onClick={() => ask(item.text)}
                  disabled={loading}
                >
                  <MessageSquare size={14} />

                  <span>
                    {item.text}
                    <small>{showingSuggested ? "Suggested" : "Asked"}</small>
                  </span>

                  <ArrowRight size={13} />
                </button>
              ))}
            </div>
          </Card>
        </aside>
      </div>

      {activeCapability === "sql" && (
        <SqlWorkspace onClose={() => setActiveCapability(null)} />
      )}

      {activeCapability === "insights" && (
        <InsightsWorkspace onClose={() => setActiveCapability(null)} />
      )}

      {activeCapability === "report" && (
        <ReportWorkspace onClose={() => setActiveCapability(null)} />
      )}

      {activeCapability === "chart" && (
        <ChartInsightWorkspace onClose={() => setActiveCapability(null)} />
      )}
    </>
  );
}

function QuickMetric({
  label,
  value,
  icon: Icon,
}) {
  return (
    <div className="quick">
      <div className="quick-icon">
        <Icon size={15} />
      </div>

      <div>
        <span>{label}</span>
        <b>{value}</b>
      </div>
    </div>
  );
}

function Health() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  /*
   * IMPORTANT:
   * The effect callback does NOT directly return Promise.all().
   * This fixes React's "destroy is not a function" error.
   */
  useEffect(() => {
    Promise.all([
      apiGet("/api/health"),
      apiGet("/api/data-quality"),
    ])
      .then(([health, quality]) => {
        setData({
          health,
          quality,
        });
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) {
    return <ErrorBox message={error} />;
  }

  if (!data) {
    return (
      <Loading text="Checking platform health..." />
    );
  }

  const h = data.health;

  const models = Object.values(
    h.ml_models || {}
  );

  const modelReady =
    models.length > 0 &&
    models.every(
      (x) => x === "loaded"
    );

  const db =
    h.database_status === "connected";

  const ai = !!h.genai_configured;

  const api =
    h.api_status === "running";

  const score = Math.round(
    ([api, db, modelReady, ai].filter(
      Boolean
    ).length /
      4) *
      100
  );

  const services = [
    [
      "Backend API",
      api,
      "Running",
    ],
    [
      "Database (MySQL)",
      db,
      "Connected",
    ],
    [
      "ML pipelines",
      modelReady,
      "All models loaded",
    ],
    [
      "GenAI",
      ai,
      ai ? "Configured" : "Not configured",
    ],
    [
      "Data quality",
      data.quality?.status ===
        "pass",
      data.quality?.status ||
        "Unknown",
    ],
  ];

  return (
    <>
      <PageHeader
        eyebrow="System health"
        title="Platform Health & Performance"
        subtitle="Monitor system status, infrastructure, services and performance metrics in real-time."
      >
        <div className="period-pill">
          Live check
          <RefreshCw size={14} />
        </div>
      </PageHeader>

      <div className="metric-grid four health-kpis">
        <MetricCard
          icon={HeartPulse}
          tone="green"
          label="System status"
          value={
            api && db
              ? "Healthy"
              : "Attention"
          }
          sub="Platform availability"
        />

        <MetricCard
          icon={Activity}
          tone="blue"
          label="Uptime"
          value="Live"
          sub="Service monitoring"
        />

        <MetricCard
          icon={Gauge}
          tone="purple"
          label="Response time"
          value="Live"
          sub="API response health"
        />

        <MetricCard
          icon={Database}
          tone="green"
          label="Database health"
          value={h.database_status}
          sub="MySQL connection"
        />
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
      <div className="health-grid">
        <Card
          title="System performance"
          icon={Activity}
        >
          <div className="performance-list">
            <div>
              <span>API availability</span>
              <b>
                {api
                  ? "Healthy"
                  : "Attention"}
              </b>
            </div>

            <div>
              <span>Database connection</span>
              <b>
                {db
                  ? "Connected"
                  : "Attention"}
              </b>
            </div>

            <div>
              <span>ML readiness</span>
              <b>
                {modelReady
                  ? "Ready"
                  : "Check"}
              </b>
            </div>

            <div>
              <span>GenAI readiness</span>
              <b>
                {ai
                  ? "Configured"
                  : "Not configured"}
              </b>
            </div>
          </div>
        </Card>

        <Card
          title="Service status"
          icon={Server}
        >
          <div className="service-table">
            {services.map(
              ([name, ok, status]) => (
                <div key={name}>
                  <span
                    className={`status-dot ${
                      ok ? "ok" : "warn"
                    }`}
                  />

                  <b>{name}</b>

                  <span>{status}</span>

                  <strong>
                    {ok ? "Ready" : "Check"}
                  </strong>
                </div>
              )
            )}
          </div>
        </Card>
      </div>

      <div className="health-grid">
        <Card
          title="Health score"
          icon={HeartPulse}
          className="score-card"
        >
          <div
            className="score-ring"
            style={{
              "--score": `${score}%`,
            }}
          >
            <div>
              <strong>{score}%</strong>
              <span>health score</span>
            </div>
          </div>

          <p>
            {score === 100
              ? "Everything is ready."
              : score >= 75
              ? "Core platform services are healthy."
              : "One or more dependencies need attention."}
          </p>
        </Card>

        <Card
          title="ML model readiness"
          icon={Sparkles}
        >
          <div className="model-list">
            {Object.entries(
              h.ml_models || {}
            ).map(([name, status]) => (
              <div key={name}>
                <span className="model-dot" />

                <b>
                  {name.replaceAll(
                    "_",
                    " "
                  )}
                </b>

                <span>{status}</span>

                <CheckCircle2 size={16} />
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="health-bottom">
        <Card
          title="Resource usage"
          icon={Gauge}
        >
          <div className="resource-bars">
            <div>
              <span>API</span>
              <i />
            </div>

            <div>
              <span>Database</span>
              <i />
            </div>

            <div>
              <span>ML services</span>
              <i />
            </div>

            <p className="muted">
              Runtime resource telemetry is not
              exposed by the current deployment.
            </p>
          </div>
        </Card>

        <Card
          title="Data quality"
          icon={ShieldCheck}
        >
          <div className="quality-head">
            <strong>
              {String(
                data.quality?.status ||
                  "unknown"
              ).toUpperCase()}
            </strong>

            <span>
              {data.quality?.checks
                ?.length || 0}{" "}
              checks
            </span>
          </div>

          {(data.quality?.checks || [])
            .slice(0, 5)
            .map((c) => (
              <div
                className="quality-row"
                key={c.check}
              >
                <CheckCircle2 size={15} />

                <span>{c.check}</span>

                <small>
                  {c.affected_rows} rows
                </small>
              </div>
            ))}
        </Card>
      </div>
    </>
  );
}

export default function App() {
  const [tab, setTab] =
    useState("overview");

  useEffect(() => {
    const fn = () =>
      setTab("customer360");

    window.addEventListener(
      "go-customer360",
      fn
    );

    return () =>
      window.removeEventListener(
        "go-customer360",
        fn
      );
  }, []);

  const page = useMemo(
    () =>
      ({
        overview: (
          <Overview
            goAI={() => setTab("ai")}
          />
        ),
        customers: <Customers />,
        customer360: <Customer360 />,
        operations: <Operations />,
        ai: <AI />,
        health: <Health />,
      }[tab]),
    [tab]
  );

  return (
    <Shell
      tab={tab}
      setTab={setTab}
    >
      {page}
    </Shell>
  );
}