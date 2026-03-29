use crate::engine::TachyonEngine;

impl TachyonEngine {
    pub fn find_lca(&self, a: usize, b: usize) -> usize {
        use std::collections::HashSet;
        let mut ancestors_a = HashSet::new();
        let mut curr = a;
        while curr != 0 {
            ancestors_a.insert(curr);
            let node = self.nodes.get(&curr).unwrap();
            if node.parents.is_empty() {
                break;
            }
            curr = node.parents[0];
        }
        ancestors_a.insert(0);

        curr = b;
        while curr != 0 {
            if ancestors_a.contains(&curr) {
                return curr;
            }
            let node = self.nodes.get(&curr).unwrap();
            if node.parents.is_empty() {
                break;
            }
            curr = node.parents[0];
        }
        0
    }

    pub fn get_shortest_path(&self, from_id: usize, to_id: usize) -> (Vec<usize>, Vec<usize>) {
        if from_id == to_id {
            return (Vec::new(), Vec::new());
        }

        let from_path = self.get_root_to_node_path(from_id);
        let to_path = self.get_root_to_node_path(to_id);

        let mut lca_idx = 0;
        for (i, (f, t)) in from_path.iter().zip(to_path.iter()).enumerate() {
            if f == t {
                lca_idx = i;
            } else {
                break;
            }
        }

        let path_up: Vec<usize> = from_path[lca_idx + 1..].iter().rev().cloned().collect();
        let path_down: Vec<usize> = to_path[lca_idx + 1..].to_vec();

        (path_up, path_down)
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
}
