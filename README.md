# netauto-clab-lab

A mixed-vendor MPLS core + 2 CPE, for practicing Ansible and Nornir
against three different automation surfaces in one topology.

```
                         r5 (AS65100, lo 5.5.5.5)
                         advertises 172.16.5.0/24
                              |  eth1
                              |  10.0.15.0/30 (eBGP)
                              |  eth3
      +---------------------r1 (RR, AS65000, lo 1.1.1.1)---------------------+
      |                     /  eth1              eth2  \                    |
      |         10.0.12.0/30                      10.0.13.0/30              |
      |                   /                              \                  |
      |     r2 (AS65000, lo 2.2.2.2)          r3 (AS65000, lo 3.3.3.3)       |
      |                   \                              /                  |
      |         10.0.24.0/30                      10.0.34.0/30              |
      |                     \  eth2              eth2  /                    |
      +---------------------r4 (AS65000, lo 4.4.4.4)---------------------+
                              |  eth3
                              |  10.0.46.0/30 (eBGP)
                              |  e1-1
                         r6 (AS65200, lo 6.6.6.6)
                         advertises 172.16.6.0/24
```

Core (r1-r4, AS65000): OSPF area 0 + real LDP-based MPLS + iBGP with r1 as
route reflector, r2/r3/r4 as clients. r5/r6 are CPEs - eBGP only, no
IGP/MPLS.

Node kinds, chosen by role/protocol fit, not arbitrarily:

| Node | Kind | Why |
|---|---|---|
| r1, r2, r4, r5 | FRR (`kind: linux`) | Open source `ldpd`, no licensing friction, majority of nodes per your ask |
| r3 | Arista cEOS | One core P-router seat. cEOS-lab has a genuine working MPLS data plane since EOS 4.31.2F ([confirmed](https://blog.ipspace.net/2024/08/arista-ceos-mpls-data-plane/)), and `arista.eos` is the most mature network automation collection out there |
| r6 | Nokia SR Linux | One CPE seat. **Not** in the LDP core - containerlab's own SR Linux docs say MPLS requires a license the free lab image doesn't include ("without the license provided, the lab will not start"), so it can't do the P-router job here. CPE is eBGP-only, which reuses the full Ansible/Nornir tooling already built for it |

You said you already have the cEOS and SR Linux images - check their
exact local tags with `docker images` and fix the two `image:` lines in
`topology/lab.clab.yml` if they don't match `ceos:4.32.0F` /
`ghcr.io/nokia/srlinux:latest`.

## Sizing on your 8 GB VM

This is a tighter budget than the earlier 3-node SR Linux lab, and the
weakest number in it is cEOS - I couldn't find a confirmed RAM figure for
it anywhere in Arista's docs (containerlab's own cEOS page doesn't
publish one either). Rough budget, native-container-class assumptions
(no vrnetlab/QEMU involved anywhere in this topology):

| | Estimate |
|---|---|
| Host/Docker/containerlab overhead | ~1-1.5 GB |
| 4x FRR | ~0.4-0.8 GB total (very light) |
| 1x SR Linux (r6) | ~0.8-1 GB |
| 1x cEOS (r3) | **unconfirmed** - budget 1.5-2 GB to be safe |
| **Total** | **~4-5.5 GB**, leaving some headroom in 8 GB - but not a lot |

Given the uncertainty on cEOS specifically, deploy and watch it rather
than trusting the estimate blind:

```bash
sudo containerlab deploy -t topology/lab.clab.yml
watch -n2 'free -h; echo; docker stats --no-stream'
```

If it's thrashing, the cheapest fallback is commenting out `r3` and its
two links in `lab.clab.yml`, confirming the other 5 nodes work, then
adding `r3` back on its own to see its actual footprint in isolation
before deciding whether to keep it.

## Deploy

```bash
cd topology
sudo containerlab deploy -t lab.clab.yml
sudo containerlab inspect -t lab.clab.yml
```

You should see all 6 nodes with their `172.100.100.1x` management IPs.

## Verify by hand first

**FRR nodes** (r1, r2, r4, r5) - no SSH, access via `docker exec`:

```bash
sudo docker exec -it clab-netauto-lab-r1 vtysh
r1# show ip ospf neighbor
r1# show mpls ldp neighbor
r1# show ip bgp summary
r1# show ip route
```

**cEOS** (r3):

```bash
ssh admin@172.100.100.13        # password: admin
r3>show ip ospf neighbor
r3>show mpls ldp neighbor
r3>show ip bgp summary
```

**SR Linux** (r6):

```bash
ssh admin@172.100.100.16        # password: NokiaSrl1!
show network-instance default protocols bgp neighbor
```

What "working" looks like: on r1, two OSPF neighbors (r2, r3) and two LDP
neighbors; on r2/r3/r4, one OSPF+LDP neighbor pair each pointing back
into the core; iBGP sessions up on all of r1/r2/r3/r4; eBGP up on
r1<->r5 and r4<->r6. `show ip route` / `show network-instance default
route-table` on any node should eventually show all four loopbacks
(1.1.1.1-4.4.4.4) plus both site prefixes (172.16.5.0/24, 172.16.6.0/24).
Fix connectivity here before touching Ansible/Nornir.

## Ansible

```bash
cd ../ansible
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements_python.txt
ansible-galaxy collection install -r requirements_ans.yml

# the structured used for this project takes into account the vault treatment for critical data, # # credentials for eos and srlinux boxes.
# the encryption step is needed for vault files:

ansible-vault encrypt group_vars/eos/vault.yml
ansible-vault encrypt group_vars/srlinux/vault.yml

### the content was just the definition of the credentials as the jinja template in vars required
# vault_eos_user: xxxx
# vault_eos_pass: xxxx

# execution without vault encription:

# ansible-playbook playbooks/01_ping.yml           # connectivity, all 3 platforms
# ansible-playbook playbooks/02_gather_facts.yml   # BGP/route state, all 3 platforms
# ansible-playbook playbooks/03_configure_interface.yml   # config push - SR Linux (r6) and eos.config for r3


# execution with vault encryption, and the config for automatic pass assigment is done using .vault_pass_netauto

# echo 'your-chosen-vault-password' > ~/.vault_pass_netauto
# chmod 600 ~/.vault_pass_netauto
# ansible-playbook playbooks/01_ping.yml --vault-password-file ~/.vault_pass_netauto

# vault_password_file = ~/.vault_pass_netauto

# ansible-vault view group_vars/eos/vault.yml     # read it, decrypted, to stdout
# ansible-vault edit group_vars/eos/vault.yml     # decrypt, open in $EDITOR, re-encrypt on save
# ansible-vault rekey group_vars/eos/vault.yml    # change the vault password later

ansible-playbook playbooks/01_ping.yml --ask-vault-pass         # connectivity, all 3 platforms
ansible-playbook playbooks/02_gather_facts.yml --ask-vault-pass   # BGP/route state, all 3 platforms
ansible-playbook playbooks/03_configure_interface.yml   # config push - SR Linux (r6) and eos.config for r3


```

The `frr` group's plays run through `community.docker`'s connection
plugin (`docker exec`, not SSH) - this only works when Ansible runs on
the same machine as containerlab, which it does here.

## Nornir

```bash
cd ../nornir
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

#  the credentials used for this lab are passed with .env 

python scripts/01_get_facts.py           # connectivity, all 3 platforms
python scripts/02_configure_interface.py # config push - SR Linux (r6) only for now
python scripts/03_backup_configs.py      # config backup - SR Linux (r6) only for now
```

`01_get_facts.py` dispatches per platform: FRR via `docker exec` +
`vtysh`, cEOS via `nornir_scrapli` (a core scrapli platform, no extra
driver needed), SR Linux via raw JSON-RPC.

## Teardown / redeploy

```bash
cd topology
sudo containerlab destroy -t lab.clab.yml    # add --cleanup to wipe state too
sudo containerlab deploy -t lab.clab.yml
```


## Where this goes next

- Config-push automation only covers SR Linux (r6) so far - extending it
  to the `frr` group (`vtysh -c "configure terminal" -c "..."`) 
- This intentionally stops at "IGP + LDP + iBGP/eBGP carrying plain IPv4
  routes" - it does not build actual MPLS L3VPN (per-customer VRFs,
  route-distinguishers, VPNv4). That's a reasonable next layer if you
  want the full SP-style picture.

