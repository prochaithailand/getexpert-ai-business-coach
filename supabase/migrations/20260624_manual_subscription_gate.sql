alter table public.users
  add column if not exists subscription_status text,
  add column if not exists subscription_plan text,
  add column if not exists subscription_started_at timestamptz,
  add column if not exists subscription_expires_at timestamptz,
  add column if not exists last_payment_at timestamptz,
  add column if not exists approved_by text,
  add column if not exists approved_at timestamptz;

update public.users
set subscription_status = 'active',
    subscription_plan = case when role in ('Leader', 'Partner') then 'Leader' else 'Member' end,
    subscription_started_at = coalesce(subscription_started_at, now()),
    subscription_expires_at = coalesce(subscription_expires_at, now() + interval '90 days')
where subscription_status is null;

alter table public.users
  alter column subscription_status set default 'pending_payment',
  alter column subscription_status set not null,
  alter column subscription_plan set default 'Member',
  alter column subscription_plan set not null;

alter table public.users drop constraint if exists users_subscription_status_check;
alter table public.users add constraint users_subscription_status_check
  check (subscription_status in ('pending_payment', 'active', 'expired', 'suspended'));
alter table public.users drop constraint if exists users_subscription_plan_check;
alter table public.users add constraint users_subscription_plan_check
  check (subscription_plan in ('Member', 'Leader'));

create or replace function public.handle_new_getexpert_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.users (
    user_id, email, full_name, role, subscription_status, subscription_plan
  )
  values (
    new.id, lower(new.email), coalesce(new.raw_user_meta_data->>'full_name', ''),
    'Member', 'pending_payment', 'Member'
  )
  on conflict (user_id) do nothing;
  return new;
end;
$$;
