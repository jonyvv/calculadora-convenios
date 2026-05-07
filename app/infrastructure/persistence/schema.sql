create table if not exists agreements (
  agreement_id text not null,
  version text not null,
  payload jsonb not null,
  primary key (agreement_id, version)
);

create table if not exists active_agreements (
  agreement_id text primary key,
  version text not null
);

create table if not exists employees (
  employee_id text primary key,
  payload jsonb not null
);

create table if not exists monthly_events (
  employee_id text not null,
  period text not null,
  payload jsonb not null,
  primary key (employee_id, period)
);
