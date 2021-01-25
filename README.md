# GutenSearch
A search engine for [Project Gutenberg](https://www.gutenberg.org/) books built with PostgreSQL and Dash. Find it running on [GutenSearch.com](https://gutensearch.com).

## Summary
### Source data
Project Gutenberg offers [mirroring via rsync](https://www.gutenberg.org/help/mirroring.html). However, in June 2016, [Allison Parrish](https://www.decontextualize.com/) released a [corpus](https://github.com/aparrish/gutenberg-dammit) of all text files and metadata up to that point in time, which was used here instead of the raw data. 

### Process
- set up the instance, firewall, etc.
- create a new Postgres database
- stream the JSON metadata into a table
- stream the raw text data
- transform the data
- start the app

## Installation
### Choosing your hardware
The below worked for a dedicated server with an Intel Atom 2.40GHz CPU, 16GB RAM and 250GB SSD. The queries are mostly CPU-bound, particularly for common phrases. The deployed app uses 128GB of its 217GB partition.

### Setting up the instance
I've only tested this on a clean install of Ubuntu 20.04.1 LTS.

You'll need the following to get started:
```
sudo apt update
sudo apt install screen
sudo apt install unzip
sudo apt install vim # not strictly necessary
sudo apt install postgresql postgresql-contrib
```

### Setting up Postgres
You can use [this guide](https://www.digitalocean.com/community/tutorials/how-to-install-and-use-postgresql-on-ubuntu-18-04). You may want to increase resources as follows:
```
vim /etc/postgresql/12/main/postgresql.conf
```

Changing the following (here shown for a server with 16GB RAM):
```
shared_buffers = 8GB # (25% of server RAM)
work_mem = 40MB # (RAM * 0.25 / 100)
maintenance_work_mem = 800MB # (RAM * 0.05)
effective_cache_size = 8GB # (RAM * 0.5)
```

### Setting up Python
As usual the app relies on an alphabet soup of libraries:
```
sudo apt install software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa
sudo apt install python3.8
sudo apt-get install python3-venv
sudo apt install python3-pip
sudo apt install libpq-dev
```

### Getting the data
#### Create project folder
mkdir gutensearch

#### Download raw data
You will want this one in a screen as it might take a while - a few minutes in a decent data centre at 30MB/s, or a night and morning from a home connection.

```
screen -S download_data
wget -c http://static.decontextualize.com/gutenberg-dammit-files-v002.zip
mv gutenberg-dammit-files-v002.zip gutensearch/gutenberg-dammit-files-v002.zip
cd gutensearch
unzip gutenberg-dammit-files-v002.zip -d gutenberg-dammit-files-v002
exit
```

#### Insert the metadata
I recommend doing this one by hand line by line, instead of passing the file to psql. Open a screen, then line-by-line `server-process-part1.sql`.

```
screen -S process_data
sudo -u postgres psql # run through server-process-part1.sql
exit
```

SQL part 1 streams the metadata JSON into a table.

#### Insert the text
This part streams the text files into an SQL file that can be run later. It may take a while so best have it in a screen.

```
screen -S app_venv
cd ~
python3 -m venv .venvs/dash
pip3 install --upgrade pip
python3 -m pip install psycopg2
python3 server-import.py # Change the path to yours first!
exit
```

#### Transform the data
This part will take the longest as 6GB zipped is expanded into more than 60GB of tables and indices. \timing for each part is included as comments in the code; on the instance mentioned earlier, you're looking at the better part of a day.

```
screen -r process_data
sudo -u postgres psql # now run through server-process-2.sql
exit
```

### Setting up the app
#### Libraries
You'll need the following:

```
pip install --upgrade pip
python3 -m pip install dash
python3 -m pip install dash_auth
python3 -m pip install pandas
python3 -m pip install sqlalchemy
python3 -m pip install networkx
python3 -m pip install gunicorn
```

#### Set up HTTPS
Follow instructions [here](https://certbot.eff.org/lets-encrypt/ubuntufocal-nginx).

Don't forget to backup the certs:
```
scp -r user@host:/etc/letsencrypt /path/to/backup/location
```

#### Set up firewall and reverse proxy
Find the relevant instructions for your provider. Mine are [here](https://www.scaleway.com/en/docs/how-to-configure-nginx-reverse-proxy/).

You'll need to set up the firewall, instructions [here](https://linuxize.com/post/how-to-setup-a-firewall-with-ufw-on-ubuntu-18-04/).

Relevant files can be found here:
```
cd /etc/nginx/sites-available
sudo vim reverse-proxy.conf # add server_name and change the port
sudo ln -s /etc/nginx/sites-available/reverse-proxy.conf /etc/nginx/sites-enabled/reverse-proxy.conf
```

#### You can now serve the app
```
screen -S app_server
gunicorn app:server -b :port --workers=17 --log-level=debug --timeout=700
```

## License
In accordance with [GutenTag's](https://www.cs.toronto.edu/~jbrooke/gutentag/) and [Gutenberg Dammit's](https://github.com/aparrish/gutenberg-dammit) license:

This work is licensed under the Creative Commons Attribution-ShareAlike 4.0 International License. To view a copy of this license, visit https://creativecommons.org/licenses/by-sa/4.0/ or send a letter to Creative Commons, 444 Castro Street, Suite 900, Mountain View, California, 94041, USA.