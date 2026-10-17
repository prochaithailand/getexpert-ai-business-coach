begin;

alter table public.users
  alter column subscription_status set default 'pending_payment';

create or replace function public.handle_new_getexpert_user()
returns trigger language plpgsql security definer set search_path = public as $$
begin
  insert into public.users (
    user_id, email, full_name, role, subscription_status, subscription_plan,
    trial_started_at, trial_ends_at, trial_used, marketing_email_opt_in
  )
  values (
    new.id,
    lower(new.email),
    coalesce(new.raw_user_meta_data->>'full_name', ''),
    'Member', 'pending_payment', 'Member',
    null, null, false,
    coalesce((new.raw_user_meta_data->>'marketing_email_opt_in')::boolean, false)
  )
  on conflict (user_id) do nothing;
  return new;
end;
$$;

-- Existing accounts and their trial/payment entitlements are unchanged.
commit;
