import React from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  Legend,
} from 'recharts';
import {
  Activity,
  Bell,
  BookOpen,
  Crosshair,
  AlertTriangle,
  TrendingUp,
  RefreshCw,
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { getDashboardStats } from '../api/stats';
import { SeverityBadge } from '../components/shared/SeverityBadge';
import { StatusBadge } from '../components/shared/StatusBadge';
import { CardSkeleton, TableSkeleton } from '../components/shared/LoadingSpinner';
import type { DashboardStats } from '../types';

const SEVERITY_COLORS: Record<string, string> = {
  critical: '#ff3b3b',
  high: '#ff8c00',
  medium: '#ffd700',
  low: '#4a9eff',
  info: '#00bcd4',
};

const StatCard: React.FC<{
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: string;
  subtitle?: string;
}> = ({ title, value, icon, color, subtitle }) => (
  <div className="cyber-card p-5 hover:border-cyber-border/80 transition-colors">
    <div className="flex items-start justify-between mb-3">
      <span className="text-xs font-medium text-cyber-muted uppercase tracking-wider">{title}</span>
      <div
        className="w-9 h-9 rounded-lg flex items-center justify-center"
        style={{ background: `${color}18`, border: `1px solid ${color}30` }}
      >
        <span style={{ color }}>{icon}</span>
      </div>
    </div>
    <div className="text-3xl font-bold text-cyber-text mb-1">{value.toLocaleString()}</div>
    {subtitle && <div className="text-xs text-cyber-muted">{subtitle}</div>}
  </div>
);

const CustomTooltip: React.FC<{
  active?: boolean;
  payload?: Array<{ color: string; name: string; value: number }>;
  label?: string;
}> = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-cyber-card border border-cyber-border rounded-lg p-3 shadow-xl">
        <p className="text-xs text-cyber-muted mb-2 font-mono">{label}</p>
        {payload.map((entry) => (
          <div key={entry.name} className="flex items-center gap-2 text-xs">
            <span
              className="w-2 h-2 rounded-full"
              style={{ background: entry.color }}
            />
            <span className="text-cyber-muted capitalize">{entry.name}:</span>
            <span className="text-cyber-text font-semibold">{entry.value}</span>
          </div>
        ))}
      </div>
    );
  }
  return null;
};

const DashboardContent: React.FC<{ data: DashboardStats }> = ({ data }) => {
  const { overview, events_over_time, severity_distribution, category_distribution, recent_alerts, top_sources } = data;

  const chartData = events_over_time.map((item) => ({
    ...item,
    time: (() => {
      try {
        return format(parseISO(item.timestamp), 'HH:mm');
      } catch {
        return item.timestamp;
      }
    })(),
  }));

  const pieData = severity_distribution.map((item) => ({
    name: item.severity,
    value: item.count,
    color: SEVERITY_COLORS[item.severity] || '#8892a4',
  }));

  return (
    <div className="space-y-6">
      {/* Stat Cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <StatCard
          title="Total Events Today"
          value={overview.total_events_today}
          icon={<Activity className="w-5 h-5" />}
          color="#00ff88"
          subtitle={`${overview.events_last_hour} in last hour`}
        />
        <StatCard
          title="Open Alerts"
          value={overview.open_alerts}
          icon={<Bell className="w-5 h-5" />}
          color="#ff3b3b"
          subtitle={`${overview.critical_alerts} critical, ${overview.high_alerts} high`}
        />
        <StatCard
          title="Active Rules"
          value={overview.active_rules}
          icon={<BookOpen className="w-5 h-5" />}
          color="#4a9eff"
          subtitle="Correlation rules running"
        />
        <StatCard
          title="Threats Detected"
          value={overview.threats_detected}
          icon={<Crosshair className="w-5 h-5" />}
          color="#ff8c00"
          subtitle="Matched threat indicators"
        />
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Events Over Time */}
        <div className="xl:col-span-2 cyber-card p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-cyber-text flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-cyber-accent" />
              Events Over Time (24h)
            </h2>
          </div>
          {chartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: -20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3148" />
                <XAxis
                  dataKey="time"
                  tick={{ fill: '#8892a4', fontSize: 11 }}
                  tickLine={false}
                  axisLine={{ stroke: '#2a3148' }}
                />
                <YAxis
                  tick={{ fill: '#8892a4', fontSize: 11 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip content={<CustomTooltip />} />
                <Legend
                  wrapperStyle={{ fontSize: 12, color: '#8892a4' }}
                  iconType="circle"
                  iconSize={8}
                />
                <Line type="monotone" dataKey="count" stroke="#00ff88" strokeWidth={2} dot={false} name="Total" />
                <Line type="monotone" dataKey="critical" stroke="#ff3b3b" strokeWidth={1.5} dot={false} name="Critical" />
                <Line type="monotone" dataKey="high" stroke="#ff8c00" strokeWidth={1.5} dot={false} name="High" />
                <Line type="monotone" dataKey="medium" stroke="#ffd700" strokeWidth={1.5} dot={false} name="Medium" />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-cyber-muted text-sm">
              No event data available
            </div>
          )}
        </div>

        {/* Severity Distribution */}
        <div className="cyber-card p-5">
          <h2 className="text-sm font-semibold text-cyber-text flex items-center gap-2 mb-4">
            <AlertTriangle className="w-4 h-4 text-cyber-accent" />
            Severity Distribution
          </h2>
          {pieData.length > 0 ? (
            <>
              <ResponsiveContainer width="100%" height={160}>
                <PieChart>
                  <Pie
                    data={pieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={70}
                    paddingAngle={2}
                    dataKey="value"
                  >
                    {pieData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value: number, name: string) => [value, name]}
                    contentStyle={{
                      background: '#1a1f2e',
                      border: '1px solid #2a3148',
                      borderRadius: '6px',
                      color: '#e2e8f0',
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
              <div className="space-y-2 mt-2">
                {pieData.map((entry) => (
                  <div key={entry.name} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full" style={{ background: entry.color }} />
                      <span className="text-cyber-muted capitalize">{entry.name}</span>
                    </div>
                    <span className="text-cyber-text font-semibold font-mono">{entry.value.toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="h-[220px] flex items-center justify-center text-cyber-muted text-sm">
              No data available
            </div>
          )}
        </div>
      </div>

      {/* Category Distribution Bar Chart */}
      {category_distribution.length > 0 && (
        <div className="cyber-card p-5">
          <h2 className="text-sm font-semibold text-cyber-text mb-4">Category Distribution</h2>
          <ResponsiveContainer width="100%" height={180}>
            <BarChart
              data={category_distribution}
              margin={{ top: 5, right: 5, bottom: 20, left: -20 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3148" />
              <XAxis
                dataKey="category"
                tick={{ fill: '#8892a4', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#2a3148' }}
                angle={-35}
                textAnchor="end"
              />
              <YAxis
                tick={{ fill: '#8892a4', fontSize: 11 }}
                tickLine={false}
                axisLine={false}
              />
              <Tooltip
                contentStyle={{
                  background: '#1a1f2e',
                  border: '1px solid #2a3148',
                  borderRadius: '6px',
                  color: '#e2e8f0',
                  fontSize: 12,
                }}
              />
              <Bar dataKey="count" fill="#00ff88" radius={[3, 3, 0, 0]} opacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Bottom Row */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {/* Recent Alerts */}
        <div className="cyber-card overflow-hidden">
          <div className="px-5 py-4 border-b border-cyber-border">
            <h2 className="text-sm font-semibold text-cyber-text flex items-center gap-2">
              <Bell className="w-4 h-4 text-cyber-accent" />
              Recent Alerts
            </h2>
          </div>
          {recent_alerts.length === 0 ? (
            <div className="py-10 text-center text-cyber-muted text-sm">No recent alerts</div>
          ) : (
            <div className="divide-y divide-cyber-border/50">
              {recent_alerts.slice(0, 10).map((alert) => (
                <div
                  key={alert.id}
                  className="px-5 py-3 hover:bg-cyber-border/20 transition-colors"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-cyber-text truncate font-medium">{alert.title}</p>
                      <p className="text-xs text-cyber-muted mt-0.5 font-mono">
                        {(() => {
                          try {
                            return format(parseISO(alert.created_at), 'MMM dd HH:mm:ss');
                          } catch {
                            return alert.created_at;
                          }
                        })()}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <SeverityBadge severity={alert.severity} size="sm" />
                      <StatusBadge status={alert.status} size="sm" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Top Source IPs */}
        <div className="cyber-card overflow-hidden">
          <div className="px-5 py-4 border-b border-cyber-border">
            <h2 className="text-sm font-semibold text-cyber-text">Top Source IPs</h2>
          </div>
          {top_sources.length === 0 ? (
            <div className="py-10 text-center text-cyber-muted text-sm">No source data</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-cyber-border/50">
                    <th className="text-left px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">
                      Source IP
                    </th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">
                      Events
                    </th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">
                      Critical
                    </th>
                    <th className="text-right px-5 py-3 text-xs font-medium text-cyber-muted uppercase tracking-wider">
                      High
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-cyber-border/30">
                  {top_sources.map((src) => (
                    <tr key={src.source_ip} className="table-row-hover">
                      <td className="px-5 py-3 font-mono text-sm text-cyber-accent">
                        {src.source_ip}
                      </td>
                      <td className="px-5 py-3 text-right text-sm font-semibold text-cyber-text">
                        {src.count.toLocaleString()}
                      </td>
                      <td className="px-5 py-3 text-right text-sm text-red-400 font-mono">
                        {src.severity_breakdown?.critical || 0}
                      </td>
                      <td className="px-5 py-3 text-right text-sm text-orange-400 font-mono">
                        {src.severity_breakdown?.high || 0}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

const Dashboard: React.FC = () => {
  const { data, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['dashboard-stats'],
    queryFn: getDashboardStats,
    refetchInterval: 30000,
  });

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-cyber-text">Dashboard</h1>
          <p className="text-sm text-cyber-muted mt-1">Security overview — auto-refreshes every 30s</p>
        </div>
        <button
          onClick={() => refetch()}
          disabled={isFetching}
          className="flex items-center gap-2 cyber-btn-secondary"
        >
          <RefreshCw className={`w-4 h-4 ${isFetching ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {isLoading && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => <CardSkeleton key={i} />)}
          </div>
          <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
            <div className="xl:col-span-2 cyber-card p-5">
              <TableSkeleton rows={5} cols={4} />
            </div>
            <div className="cyber-card p-5">
              <TableSkeleton rows={5} cols={2} />
            </div>
          </div>
        </div>
      )}

      {isError && (
        <div className="cyber-card p-8 text-center">
          <AlertTriangle className="w-10 h-10 text-cyber-danger mx-auto mb-3" />
          <p className="text-cyber-danger font-medium">Failed to load dashboard</p>
          <p className="text-cyber-muted text-sm mt-1">{(error as Error).message}</p>
          <button onClick={() => refetch()} className="cyber-btn-secondary mt-4">
            Retry
          </button>
        </div>
      )}

      {data && <DashboardContent data={data} />}
    </div>
  );
};

export default Dashboard;
