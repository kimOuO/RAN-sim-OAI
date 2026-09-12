'use client';

import { LogFilters, CATEGORY_GROUPS, GROUP_LABEL } from '@/lib/logStats';

interface Props {
  filters: LogFilters;
  onChange: (next: LogFilters) => void;
  autoScroll: boolean;
  onAutoScrollChange: (v: boolean) => void;
  matchedCount: number;
  totalCount: number;
}

export function LogFilterBar({
  filters, onChange, autoScroll, onAutoScrollChange, matchedCount, totalCount,
}: Props) {
  const update = <K extends keyof LogFilters>(key: K, value: LogFilters[K]) => {
    onChange({ ...filters, [key]: value });
  };

  const filterActive =
    filters.service !== 'all' ||
    filters.group !== 'all' ||
    filters.status !== 'all' ||
    filters.hideTick;

  return (
    <div style={{
      display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center',
      padding: '10px 12px', background: '#0b1220', borderRadius: 6,
      border: '1px solid #374151', marginBottom: 12, fontSize: 12,
      color: '#cbd5e1',
    }}>
      <Field label="Service">
        <select
          value={filters.service}
          onChange={(e) => update('service', e.target.value as LogFilters['service'])}
          style={selectStyle}
        >
          <option value="all">all</option>
          <option value="CU">CU</option>
          <option value="DU">DU</option>
          <option value="RU">RU</option>
        </select>
      </Field>

      <Field label="Group">
        <select
          value={filters.group}
          onChange={(e) => update('group', e.target.value as LogFilters['group'])}
          style={selectStyle}
        >
          <option value="all">all</option>
          {CATEGORY_GROUPS.map((g) => (
            <option key={g} value={g}>{GROUP_LABEL[g]}</option>
          ))}
        </select>
      </Field>

      <Field label="Status">
        <select
          value={filters.status}
          onChange={(e) => update('status', e.target.value as LogFilters['status'])}
          style={selectStyle}
        >
          <option value="all">all</option>
          <option value="2xx">2xx ✓</option>
          <option value="4xx">4xx ⚠</option>
          <option value="5xx">5xx ✗</option>
        </select>
      </Field>

      <label style={checkboxLabel}>
        <input
          type="checkbox"
          checked={filters.hideTick}
          onChange={(e) => update('hideTick', e.target.checked)}
        />
        hide Tick_*
      </label>

      <label style={checkboxLabel}>
        <input
          type="checkbox"
          checked={autoScroll}
          onChange={(e) => onAutoScrollChange(e.target.checked)}
        />
        auto-scroll
      </label>

      {filterActive && (
        <button
          onClick={() => onChange({ service: 'all', group: 'all', status: 'all', hideTick: false })}
          style={{
            fontSize: 11, padding: '3px 8px', borderRadius: 4,
            border: '1px solid #374151', background: '#1f2937',
            color: '#cbd5e1', cursor: 'pointer',
          }}
        >
          clear filters
        </button>
      )}

      <div style={{ marginLeft: 'auto', fontSize: 11, color: '#9ca3af' }}>
        showing <strong style={{ color: '#cbd5e1' }}>{matchedCount}</strong> / {totalCount} messages
      </div>
    </div>
  );
}

const selectStyle: React.CSSProperties = {
  padding: '3px 6px',
  borderRadius: 4,
  border: '1px solid #374151',
  fontSize: 12,
  background: '#1f2937',
  color: '#cbd5e1',
  cursor: 'pointer',
};

const checkboxLabel: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, cursor: 'pointer', color: '#cbd5e1',
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <span style={{ fontSize: 11, color: '#9ca3af', fontWeight: 600 }}>{label}:</span>
      {children}
    </label>
  );
}
