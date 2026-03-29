use crate::engine::TachyonEngine;

impl TachyonEngine {
    pub fn find_lca(&self, a: usize, b: usize) -> usize {
        use std::collections::HashSet;
        let mut ancestors_a = HashSet::new();
        let mut curr = Some(a);
        while let Some(id) = curr {
            ancestors_a.insert(id);
            curr = self.nodes.get(&id).and_then(|n| n.parents.first().cloned());
        }

        let mut curr = Some(b);
        while let Some(id) = curr {
            if ancestors_a.contains(&id) {
                return id;
            }
            curr = self.nodes.get(&id).and_then(|n| n.parents.first().cloned());
        }
        0 // Fallback to Node 0, but it might be pruned
    }

    pub fn get_shortest_path(&self, from_id: usize, to_id: usize) -> (Vec<usize>, Vec<usize>) {
        if from_id == to_id {
            return (Vec::new(), Vec::new());
        }

        let from_path = self.get_root_to_node_path(from_id);
        let to_path = self.get_root_to_node_path(to_id);

        let mut lca_idx = None;
        for (i, (f, t)) in from_path.iter().zip(to_path.iter()).enumerate() {
            if f == t {
                lca_idx = Some(i);
            } else {
                break;
            }
        }

        match lca_idx {
            Some(idx) => {
                let path_up: Vec<usize> = from_path[idx + 1..].iter().rev().cloned().collect();
                let path_down: Vec<usize> = to_path[idx + 1..].to_vec();
                (path_up, path_down)
            }
            None => {
                // Disconnected islands. Undo entire from_path, redo entire to_path.
                let path_up: Vec<usize> = from_path.iter().rev().cloned().collect();
                let path_down: Vec<usize> = to_path.to_vec();
                (path_up, path_down)
            }
        }
    }

    pub fn get_root_to_node_path(&self, node_id: usize) -> Vec<usize> {
        let mut path = Vec::new();
        let mut curr = Some(node_id);
        while let Some(id) = curr {
            path.push(id);
            curr = self.nodes.get(&id).and_then(|n| n.parents.first().cloned());
        }
        path.reverse();
        path
    }

    pub fn get_path_between(&self, base_id: usize, head_id: usize) -> Vec<usize> {
        let mut path = Vec::new();
        let mut curr = head_id;
        while curr != base_id && curr != 0 {
            path.push(curr);
            let node = self.nodes.get(&curr).unwrap();
            if node.parents.is_empty() {
                break;
            }
            curr = node.parents[0];
        }
        path.reverse();
        path
    }

    pub fn gc(&mut self) {
        use std::collections::HashSet;
        let mut reachable = HashSet::new();
        let mut worklist: Vec<usize> = self.node_labels.values().cloned().collect();
        for &id in self.branch_labels.values() {
            worklist.push(id);
        }
        worklist.push(self.current_node);

        while let Some(id) = worklist.pop() {
            if reachable.insert(id) {
                if let Some(node) = self.nodes.get(&id) {
                    for &parent_id in &node.parents {
                        worklist.push(parent_id);
                    }
                }
            }
        }

        self.nodes.retain(|id, _| reachable.contains(id));
    }

    pub fn prune(&mut self) {
        if self.nodes.len() <= self.max_nodes {
            return;
        }

        // 1. Simple GC first
        self.gc();
        if self.nodes.len() <= self.max_nodes {
            return;
        }

        // 2. Identify and protect ancestors of current Head and Labeled moments
        use std::collections::HashSet;
        let mut protected = HashSet::new();
        let mut seeds: Vec<usize> = self.node_labels.values().cloned().collect();
        for &id in self.branch_labels.values() {
            seeds.push(id);
        }
        seeds.push(self.current_node);

        while let Some(id) = seeds.pop() {
            if protected.insert(id) {
                if let Some(node) = self.nodes.get(&id) {
                    for &parent_id in &node.parents {
                        seeds.push(parent_id);
                    }
                }
            }
        }

        // 3. Only prune nodes that exceed the max_nodes limit.
        // We pick the oldest nodes in the graph that are candidates.
        let mut all_ids: Vec<usize> = self.nodes.keys().cloned().collect();
        all_ids.sort();

        let to_remove_count = self.nodes.len() - self.max_nodes;
        // Priority for pruning:
        // A. If a node is NOT in the `protected` set (GC should have grabbed it, but just in case)
        // B. Oldest ancestors of current branches (this moves the root forward)

        let mut prune_targets = Vec::new();
        for &id in &all_ids {
            if prune_targets.len() >= to_remove_count {
                break;
            }
            // We can prune any node as long as we merge its deltas into its children.
            // But we prefer NOT pruning the current_node or active branch heads.
            let is_branch_head = self.branch_labels.values().any(|&bid| bid == id);
            let is_node_label = self.node_labels.values().any(|&nid| nid == id);

            if id != self.current_node && !is_branch_head && !is_node_label {
                prune_targets.push(id);
            }
        }

        if prune_targets.is_empty() {
            return;
        }

        let prune_set: HashSet<usize> = prune_targets.iter().cloned().collect();

        // 4. Merge deltas into children before removing
        let mut child_map: std::collections::HashMap<usize, Vec<usize>> =
            std::collections::HashMap::new();
        for (id, node) in &self.nodes {
            if !prune_set.contains(id) {
                for &p_id in &node.parents {
                    if prune_set.contains(&p_id) {
                        child_map.entry(p_id).or_default().push(*id);
                    }
                }
            }
        }

        for &p_id in &prune_targets {
            if let Some(p_node) = self.nodes.get(&p_id) {
                let p_deltas = p_node.deltas.clone();
                if let Some(children) = child_map.get(&p_id) {
                    for &c_id in children {
                        if let Some(c_node) = self.nodes.get_mut(&c_id) {
                            let mut merged = p_deltas.clone();
                            merged.append(&mut c_node.deltas);
                            c_node.deltas = merged;
                        }
                    }
                }
            }
        }

        // Update parents of surviving nodes
        for node in self.nodes.values_mut() {
            node.parents.retain(|p| !prune_set.contains(p));
        }

        // Remove pruned nodes
        for id in prune_targets {
            self.nodes.remove(&id);
        }
    }
}
