alter table public.users
  add column if not exists trial_started_at timestamptz,
  add column if not exists trial_ends_at timestamptz,
  add column if not exists trial_used boolean not null default false;

alter table public.users drop constraint if exists users_subscription_status_check;
alter table public.users add constraint users_subscription_status_check
  check (subscription_status in ('trialing', 'pending_payment', 'active', 'expired', 'suspended'));

alter table public.users
  alter column subscription_status set default 'trialing';

create or replace function public.handle_new_getexpert_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.users (
    user_id,
    email,
    full_name,
    role,
    subscription_status,
    subscription_plan,
    trial_started_at,
    trial_ends_at,
    trial_used
  )
  values (
    new.id,
    lower(new.email),
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    'Member',
    'trialing',
    'Member',
    now(),
    now() + interval '7 days',
    true
  )
  on conflict (user_id) do nothing;
  return new;
end;
$$;

-- Existing accounts retain their current subscription status.
-- Mark existing accounts as having consumed any historical trial entitlement
-- so the trial cannot be restarted by later profile or role updates.
update public.users
set trial_used = true
where trial_used = false
  and created_at < now();
