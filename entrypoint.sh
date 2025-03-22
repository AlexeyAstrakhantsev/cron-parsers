#!/bin/bash
service cron start
tail -f /var/log/cron.log