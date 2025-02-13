# Contributing

![GitHub License](https://img.shields.io/github/license/canonical/parca-scrape-target-operator)
![GitHub Commit Activity](https://img.shields.io/github/commit-activity/y/canonical/parca-scrape-target-operator)
![GitHub Lines of Code](https://img.shields.io/tokei/lines/github/canonical/parca-scrape-target-operator)
![GitHub Issues](https://img.shields.io/github/issues/canonical/parca-scrape-target-operator)
![GitHub PRs](https://img.shields.io/github/issues-pr/canonical/parca-scrape-target-operator)
![GitHub Contributors](https://img.shields.io/github/contributors/canonical/parca-scrape-target-operator)
![GitHub Watchers](https://img.shields.io/github/watchers/canonical/parca-scrape-target-operator?style=social)

This documents explains the processes and practices recommended for contributing enhancements to this operator.

- Generally, before developing enhancements to this charm, you should consider [opening an issue](https://github.com/canonical/parca-scrape-target-operator/issues) explaining your use case.
- If you would like to chat with us about your use-cases or proposed implementation, you can reach us at [Canonical Mattermost public channel](https://chat.charmhub.io/charmhub/channels/charm-dev) or [Discourse](https://discourse.charmhub.io/).
- Familiarising yourself with the [Charmed Operator Framework](https://juju.is/docs/sdk) library will help you a lot when working on new features or bug fixes.
- All enhancements require review before being merged. Code review typically examines:
  - code quality
  - test robustness
  - user experience for Juju administrators this charm
- When evaluating design decisions, we optimize for the following personas, in descending order of priority:
  - the Juju administrator
  - charm authors that need to integrate with this charm through relations
  - the contributors to this charm's codebase
- Please help us out in ensuring easy to review branches by rebasing your pull request branch onto the `main` branch. This also avoids merge commits and creates a linear Git commit history.

## Notable design decisions

This is a workloadless charm whose purpose is to configure a parca scrape job for a target that is not charmed or can't natively be integrated with parca.

## Developing

You can use the environments created by `tox` for development:

```shell
tox --notest -e unit
source .tox/unit/bin/activate
```

### Testing

```shell
tox -e fmt           # update your code according to linting rules
tox -e lint          # code style
tox -e unit          # unit tests
tox -e integration   # integration tests
tox                  # runs 'lint' and 'unit' environments
```

### Setup

These instructions assume you will run the charm on [`microk8s`](https://microk8s.io), and relies on the `dns`, `storage`, `registry` and `metallb` plugins:

```sh
sudo snap install microk8s --classic
microk8s enable storage dns
microk8s enable metallb 192.168.0.10-192.168.0.100  # You will likely want to change these IP ranges
```

The `storage` and `dns` plugins are required machinery for most Juju charms running on K8s.
This charm is no different.
The `metallb` plugin is needed so that the Traefik ingress will receive on its service, which is of type `LoadBalancer`, an external IP it can propagate to the proxied applications.

The setup for Juju consists as follows:

```sh
sudo snap install juju --classic
juju bootstrap microk8s development
```

### Build

Build the charm in this git repository using:

```shell
charmcraft pack
```

### Deploy

```sh
# Create a model
juju add-model parca-dev
# Enable DEBUG logging
juju model-config logging-config="<root>=INFO;unit=DEBUG"
juju deploy ./parca-scrape-target_ubuntu@22.04-amd64.charm parca-scrape-target
```
