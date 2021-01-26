  -----------
-- After running server-import.py, continue:
  -----------

\c gutensearch

create schema gutenberg;
  
-- Assumes you've created a read-only user gutensearch_read_only. This gives it the read only privileges.
grant usage on schema gutenberg to gutensearch_read_only;
alter default privileges in schema gutenberg grant select on tables to gutensearch_read_only;
alter default privileges in schema gutenberg grant select on sequences to gutensearch_read_only;
grant select on all tables in schema gutenberg to gutensearch_read_only;
grant select on all sequences in schema gutenberg to gutensearch_read_only;

-- Change to your local path
\i '/path/to/gutensearch/content_insert.sql'

create table gutenberg_raw.lengths as select num, length(content) as length from gutenberg_raw.content_raw;
-- SELECT 50729
-- Time: 441927.871 ms (07:21.928)

create table gutenberg.all_data as
  select
  a.*
  , b.length
  , c.content
  from 
  gutenberg_raw.metadata_columns a
  inner join gutenberg_raw.lengths b on a.num = b.num
  inner join gutenberg_raw.content_raw c on b.num = c.num
  order by num asc;
-- SELECT 50729
-- Time: 359083.717 ms (05:59.084)
  
alter table gutenberg.all_data add primary key (num);
create index on gutenberg.all_data (language);

-- Because each book has too many unique lexemes and sometimes is just too long, we need to split books into paragraphs. A period followed by a newline is usually a new paragraph.
create table gutenberg.paragraphs as
with paragraphs as (select num, unnest(string_to_array(content, E'.\n')) as paragraph from gutenberg.all_data)
select
num
, paragraph
, length(paragraph) as paragraph_length
from paragraphs;
-- SELECT 43845406
-- Time: 1462906.498 ms (24:22.906)

create index on gutenberg.paragraphs (num); -- Time: 211714.656 ms (03:31.715)
create index on gutenberg.paragraphs (paragraph_length); -- Time: 185284.889 ms (03:05.285)
alter table gutenberg.paragraphs add foreign key (num) references gutenberg.all_data (num); -- Time: 97927.931 ms (01:37.928)

/*
This approach of splitting with E'.\n' leaves us only with these books to handle:

select a.num, a.title, a.language, case when language in ('English', 'French', 'German') then language else 'Other' end as language, b.paragraph_length from gutenberg.all_data a inner join gutenberg.paragraphs b on a.num = b.num where b.paragraph_length <> 0 order by paragraph_length desc limit 30;

  num  |                  title                   | language | language | paragraph_length 
-------+--------------------------------------------------------------------------------------------------------------------------------------------------+----------+----------+------------------
  8294 | The World English Bible (WEB):           | English  | English  |          4691208
   812 | Catalan's Constant to 1,500,000 Places   |          | Other    |          1538471
   744 | The Golden Mean                          | English  | English  |          1012528
   127 | The Number "e"                           | English  | English  |          1012525
 51155 | A Complete Dictionary of Synonyms and Antonyms  or, Synonyms and Words of Opposite Meaning   | English  | English  |          1005729
  2583 | The Value of Zeta(3) to 1,000,000 places                                                     | English  | English  |           992951
 49875 | History of the 2/6th (Rifle) Battn.      | English  | English  |           786276
    65 | The First 100,000 Prime Numbers          | English  | English  |           721213

49875, 51155, 8294 can be split with ./n.
127, 744, 812, 2583 are just a block of numbers, so we will ignore them.
65 is a list of primes separated by /n, which can also be ignored.
*/

begin;
-- Insert the newly formed paragraphs:
insert into gutenberg.paragraphs (num, paragraph, paragraph_length)
  with paragraphs as (select num, unnest(string_to_array(paragraph, E'.\n')) as paragraph from gutenberg.paragraphs where num in (49875, 51155, 8294))
  select 
  num
  , paragraph
  , length(paragraph) as paragraph_length
  from paragraphs;
-- Delete the old paragraphs:
delete from gutenberg.paragraphs 
  where paragraph_length > 721212;
commit;

-- This fills in ts_vector values using the text language (if available for FTS). Longest to run, at almost 8 hours.
alter table gutenberg.paragraphs
add column textsearchable_index_col tsvector;
update gutenberg.paragraphs
set textsearchable_index_col = to_tsvector(b.cfgname::regconfig, coalesce(paragraph, ' '))
from
gutenberg.all_data a 
inner join pg_ts_config b on lower(a.language) = b.cfgname 
where gutenberg.paragraphs.num = a.num;
-- UPDATE 43222133
-- Time: 28745153.375 ms (07:59:05.153)

create index textsearch_paragraph_idx on gutenberg.paragraphs using gin (textsearchable_index_col);
-- Time: 8567056.829 ms (02:22:47.057)

-- This denormalisation is necessary for fast querying.
ALTER TABLE gutenberg.paragraphs
ADD COLUMN language regconfig;
UPDATE gutenberg.paragraphs
SET language = b.cfgname::regconfig
from
gutenberg.all_data a 
inner join pg_ts_config b on lower(a.language) = b.cfgname 
where gutenberg.paragraphs.num = a.num;
create index on gutenberg.paragraphs (language);
-- Time: 1071239.477 ms (17:51.239)

-- Query is the author, matching is 'simple'
create table gutenberg.mentioned_authors as
select
c.author as mentioned_author
, a.author as mentioned_by
, count(distinct a.num) as books_mentioned_in
--, string_agg(distinct a.title, ', ') as books_mentioned_in_titles
from gutenberg.all_data a inner join gutenberg.paragraphs b on a.num = b.num
inner join (select author, count(distinct num) from gutenberg.all_data where author is not null and author not in ('Various', 'Unknown', 'Anonymous', 'Jr.', 'L.', 'Peer', 'Dom', 'British Museum', 'Clara', 'Morgan', 'Duchess', 'Baker', 'Elizabeth', 'Hale', 'R. H.', 'G. W.', 'W. B.', 'W. M.', 'Wang', 'Wu', 'V. M.', 'F.R.G.S.') group by author order by count desc) c 
on b.textsearchable_index_col @@ phraseto_tsquery('simple'::regconfig, c.author)
where c.author is not null and a.author is not null
group by c.author, a.author
order by books_mentioned_in desc;
-- Time: 617991.301 ms (10:17.991)

alter table gutenberg.mentioned_authors add primary key (mentioned_author, mentioned_by);
-- Time: 2484.102 ms (00:02.484)