-- This assumes you already created a database called gutensearch.
\c gutensearch
create schema gutenberg_raw;

-- The book metadata contains both metadata and the book ID we will need later.
create table gutenberg_raw.metadata_raw
  (metadata json);

-- Insert metadata ( https://stackoverflow.com/a/48396608 | https://www.postgresql.org/docs/current/app-psql.html#APP-PSQL-INTERPOLATION)
-- Change this path to yours.
begin;
\set content `cat /path/to/gutensearch/gutenberg-dammit-files-v002/gutenberg-dammit-files/gutenberg-metadata.json`
create temp table t (j json) on commit drop;
insert into t values (:'content');
insert into gutenberg_raw.metadata_raw (metadata) select json_array_elements(j) from t;
commit;

create table gutenberg_raw.metadata_columns
  (
    num integer primary key
    , author text
    , author_birth text
    , author_death text
    , author_given text
    , author_surname text
    , copyright_status text
    , language text
    , loc_class text
    , subject text
    , title text
    , charset text
    , gd_num_padded text
    , gd_path text
    , href text
  );
  
create function q_to_null(q text) returns text as $$
  begin
      return case when q = '?' then null else q end;
  end;
  $$ language plpgsql;

insert into gutenberg_raw.metadata_columns (num, author, author_birth, author_death, author_given, author_surname, copyright_status, language, loc_class, subject, title, charset, gd_num_padded, gd_path, href)
  select
  cast(metadata#>>'{Num}' as integer)
  ,q_to_null(metadata#>>'{Author,0}')
  ,q_to_null(metadata#>>'{Author Birth,0}')
  ,q_to_null(metadata#>>'{Author Death,0}')
  ,q_to_null(metadata#>>'{Author Given,0}')
  ,q_to_null(metadata#>>'{Author Surname,0}')
  ,q_to_null(metadata#>>'{Copyright Status,0}')
  ,q_to_null(metadata#>>'{Language,0}')
  ,q_to_null(metadata#>>'{LoC Class,0}')
  ,q_to_null(metadata#>>'{Subject,0}')
  ,q_to_null(metadata#>>'{Title,0}')
  ,q_to_null(metadata#>>'{charset}')
  ,q_to_null(metadata#>>'{gd-num-padded}')
  ,q_to_null(metadata#>>'{gd-path}')
  ,q_to_null(metadata#>>'{href}')
  from gutenberg_raw.metadata_raw;

create table gutenberg_raw.content_raw
  (num integer primary key, content text);