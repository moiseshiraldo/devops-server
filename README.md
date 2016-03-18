# DevOps Server

Fabric commands to deploy a DevOps server containing a monitoring dashboard (grafana, graphite and statsd), a crash reporting platform (Sentry) and a continuous integration server (Jenkins).

## Requirements
A Debian-based system for the server, an SSH connection and Fabric. The installation has been tested on an AWS EC2 instance with the latest Ubuntu AMI.

## Stack

| Software        | Description               | Listening port  | Config directory |
| --------------- |---------------------------| ---------------:| ---------------- |
| [Graphite](https://github.com/graphite-project/graphite-web)        | Real-time graphing system | 8080 TCP        | GRAPHITE_DIR     |
| [Carbon](https://github.com/graphite-project/carbon)          | Metrics aggregation       | 2003 TCP        | GRAPHITE_DIR     |
| [Whisper](https://github.com/graphite-project/whisper)         | File-based time-series DB | N/A             | GRAPHITE_DIR     |
| [Grafana](https://github.com/grafana/grafana)         | Dasboard builder          | 3000 TCP        | /etc/grafana     |
| [Statsd](https://github.com/etsy/statsd)          | Stats colleciton daemon   | 8125 UDP        | /etc/statsd      |
| [Sentry](https://github.com/getsentry/sentry)          | Crash reporting platform  | 4000 TCP        | SENTRY_DIR       |
| [Jenkins](https://github.com/jenkinsci/jenkins)         | Continuous integration    | 8081 TCP        | JENKINS_DIR      |
| [Nginx](http://nginx.org/)           | Web/proxy server          | 80/443 TCP      | /etc/nginx       |

### Diagram
![Stack diagram](/stack.png?raw=true)

## Configuration

The configuration previous to the installation is done on the `settings.py` file. You must set the host and user to make the SSH connection to the server and the directories to install the different components. Note that the user must have sudo privileges on the server and write permission to create the directories.

You also have to set the domain name for the server and whether nginx will use SSL or not. If it does, by default the SSL certificate will be generated using [Letsencrypt](https://letsencrypt.org/), though you can just spicify the path to the certificate.

## Installation

Go to the directory of the component you want to install and execute the `full_installation` fabric command. For example, to install the monitoring dashboard:

```
$ cd dashboard
$ fab full_installation
```
