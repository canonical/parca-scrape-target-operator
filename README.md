# Parca Scrape Target Operator

## Description

The Parca Scrape Target allows the [Parca Operator](https://charmhub.io/parca) and [Parca
Kubernetes Operator](https://charmhub.io/parca-k8s) to scrape applications for profiles that do not
exist within the Juju model. While the preferred mode of operation for these operators is to be
related to an application that is a first-class citizen in the Juju model, often in the enterprise
there are pre-existing applications that need to interact with newly deployed Juju models.

## Usage

```bash
# Deploy Parca on Kubernetes
juju deploy parca-k8s parca

# Or on machines
juju deploy parca parca

# Deploy parca-scrape-target
juju deploy parca-scrape-target

# Configure the scrape target
juju config parca-scrape-target targets="10.28.135.26:6080"

# Relate parca and parca-scrape target to configure parca to scrape the external target
juju relate parca parca-scrape-target
```

## Relations

This charm can be related to any application that consumes the `parca_scrape` relation interface.

In general, it is expected that this is Parca on Kubernetes/Machines, but more information can be
found about how to integrate this relation interface into your application in the `parca_scrape`
[library docs](https://charmhub.io/parca/libraries/parca_scrape)
