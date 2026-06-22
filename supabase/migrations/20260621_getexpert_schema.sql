create extension if not exists pgcrypto;

create table if not exists public.users (
  user_id uuid primary key references auth.users(id) on delete cascade,
  email text not null unique,
  full_name text not null default '',
  role text not null default 'Member' check (role in ('Member', 'Leader', 'Admin')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.teams (
  team_id text primary key,
  team_data jsonb not null default '{}'::jsonb,
  updated_by text,
  updated_at timestamptz not null default now()
);

create table if not exists public.member_profiles (
  email text primary key references public.users(email) on update cascade on delete cascade,
  team_id text references public.teams(team_id) on update cascade on delete set null,
  profile_data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

create table if not exists public.prospects (
  email text not null references public.users(email) on update cascade on delete cascade,
  prospect_id text not null,
  prospect_data jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now(),
  primary key (email, prospect_id)
);

create table if not exists public.workplan_targets (
  email text not null references public.users(email) on update cascade on delete cascade,
  target_type text not null check (target_type in ('sponsor', 'team_points', 'income')),
  week integer not null check (week between 1 and 12),
  target numeric not null default 0,
  actual numeric not null default 0,
  updated_at timestamptz not null default now(),
  primary key (email, target_type, week)
);

create table if not exists public.thirty_day_progress (
  email text not null references public.users(email) on update cascade on delete cascade,
  day integer not null check (day between 1 and 30),
  completed boolean not null default false,
  plan_item jsonb,
  profile_signature jsonb,
  updated_at timestamptz not null default now(),
  primary key (email, day)
);

create table if not exists public.pp_scores (
  email text primary key references public.users(email) on update cascade on delete cascade,
  pp_score integer not null default 0 check (pp_score >= 0),
  updated_at timestamptz not null default now()
);

create table if not exists public.content_history (
  id uuid primary key default gen_random_uuid(),
  email text not null references public.users(email) on update cascade on delete cascade,
  channel text not null,
  content text not null,
  created_at timestamptz not null default now()
);

create table if not exists public.ai_chat_history (
  id uuid primary key default gen_random_uuid(),
  email text not null references public.users(email) on update cascade on delete cascade,
  role text not null check (role in ('user', 'assistant')),
  content text not null,
  sources jsonb not null default '[]'::jsonb,
  chat_type text not null default 'member' check (chat_type in ('member', 'team')),
  team_id text,
  created_at timestamptz not null default now()
);

create or replace function public.handle_new_getexpert_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.users (user_id, email, full_name, role)
  values (new.id, lower(new.email), coalesce(new.raw_user_meta_data->>'full_name', ''), 'Member')
  on conflict (user_id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created_getexpert on auth.users;
create trigger on_auth_user_created_getexpert
after insert on auth.users for each row execute function public.handle_new_getexpert_user();

create or replace function public.getexpert_is_admin()
returns boolean language sql stable security definer set search_path = public as $$
  select exists(select 1 from public.users where user_id = auth.uid() and role = 'Admin');
$$;

create or replace function public.getexpert_can_view_member(target_email text)
returns boolean language sql stable security definer set search_path = public as $$
  select
    target_email = lower(auth.email())
    or public.getexpert_is_admin()
    or exists (
      select 1
      from public.users leader
      join public.member_profiles lp on lp.email = leader.email
      join public.member_profiles tp on tp.email = target_email
      where leader.user_id = auth.uid() and leader.role = 'Leader' and lp.team_id = tp.team_id
    );
$$;

alter table public.users enable row level security;
alter table public.member_profiles enable row level security;
alter table public.teams enable row level security;
alter table public.prospects enable row level security;
alter table public.workplan_targets enable row level security;
alter table public.thirty_day_progress enable row level security;
alter table public.pp_scores enable row level security;
alter table public.content_history enable row level security;
alter table public.ai_chat_history enable row level security;

drop policy if exists users_select on public.users;
create policy users_select on public.users for select to authenticated
using (email = lower(auth.email()) or public.getexpert_is_admin());
drop policy if exists users_admin_update on public.users;
create policy users_admin_update on public.users for update to authenticated
using (public.getexpert_is_admin()) with check (role in ('Member', 'Leader', 'Admin'));

drop policy if exists teams_read on public.teams;
create policy teams_read on public.teams for select to authenticated using (true);
drop policy if exists teams_admin_insert on public.teams;
create policy teams_admin_insert on public.teams for insert to authenticated with check (public.getexpert_is_admin());
drop policy if exists teams_admin_update on public.teams;
create policy teams_admin_update on public.teams for update to authenticated using (public.getexpert_is_admin());
drop policy if exists teams_admin_delete on public.teams;
create policy teams_admin_delete on public.teams for delete to authenticated using (public.getexpert_is_admin());

drop policy if exists profiles_read on public.member_profiles;
create policy profiles_read on public.member_profiles for select to authenticated
using (public.getexpert_can_view_member(email));
drop policy if exists profiles_own_insert on public.member_profiles;
create policy profiles_own_insert on public.member_profiles for insert to authenticated
with check (email = lower(auth.email()));
drop policy if exists profiles_own_update on public.member_profiles;
create policy profiles_own_update on public.member_profiles for update to authenticated
using (email = lower(auth.email())) with check (email = lower(auth.email()));
drop policy if exists profiles_admin_update on public.member_profiles;
create policy profiles_admin_update on public.member_profiles for update to authenticated
using (public.getexpert_is_admin()) with check (public.getexpert_is_admin());

do $$
declare table_name text;
begin
  foreach table_name in array array['prospects','workplan_targets','thirty_day_progress','pp_scores','content_history','ai_chat_history']
  loop
    execute format('drop policy if exists %I on public.%I', table_name || '_read', table_name);
    execute format('create policy %I on public.%I for select to authenticated using (public.getexpert_can_view_member(email))', table_name || '_read', table_name);
    execute format('drop policy if exists %I on public.%I', table_name || '_own_insert', table_name);
    execute format('create policy %I on public.%I for insert to authenticated with check (email = lower(auth.email()))', table_name || '_own_insert', table_name);
    execute format('drop policy if exists %I on public.%I', table_name || '_own_update', table_name);
    execute format('create policy %I on public.%I for update to authenticated using (email = lower(auth.email())) with check (email = lower(auth.email()))', table_name || '_own_update', table_name);
    execute format('drop policy if exists %I on public.%I', table_name || '_own_delete', table_name);
    execute format('create policy %I on public.%I for delete to authenticated using (email = lower(auth.email()))', table_name || '_own_delete', table_name);
  end loop;
end $$;

create index if not exists member_profiles_team_idx on public.member_profiles(team_id);
create index if not exists prospects_email_idx on public.prospects(email);
create index if not exists ai_chat_history_email_created_idx on public.ai_chat_history(email, created_at);

grant select, insert, update, delete on all tables in schema public to authenticated;
grant execute on function public.getexpert_is_admin() to authenticated;
grant execute on function public.getexpert_can_view_member(text) to authenticated;
