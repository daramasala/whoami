drop table if exists results;
create table results (
    submitter_id integer not null,
    subject_id integer not null,
    adjective text not null
);

-- this index is used for fetch queries
drop index if exists results_ids_idx;
create index results_ids_idx on results (
    subject_id,
    submitter_id
);


-- this index verifies there are no double rows in the db
drop index if exists results_unique_idx;
create unique index results_unique_idx on results (
    subject_id,
    submitter_id,
    adjective
);