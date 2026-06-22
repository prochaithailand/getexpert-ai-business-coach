alter table public.thirty_day_progress
  add column if not exists plan_item jsonb,
  add column if not exists profile_signature jsonb;

comment on column public.thirty_day_progress.plan_item is
  'Generated action-plan content for this day.';

comment on column public.thirty_day_progress.profile_signature is
  'Member profile signature used to generate the current 30-day plan.';
